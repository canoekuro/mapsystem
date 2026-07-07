"""
PNG composition for mapsystem (SPEC §8.3).

The downloaded PNG is a single 1280x720 image combining the purple header
band, the map, and the facility list, composed with Pillow.

The map image is rendered browserlessly by ``lib.static_map`` (pure-Python
OSM tiles), so this works on Databricks Apps where no browser can be
installed.  Map acquisition and composition stay separate so the composition
is a pure, locally testable function:

    render_static_map(...)      -- store -> map-only PNG bytes (lib.static_map)
    compose_canvas(map_png, ..) -- pure: map PNG bytes -> composite PNG bytes
    build_png(...)              -- compose_canvas(render_static_map(...), ...)
"""

import io
import logging
import os

from PIL import Image, ImageDraw, ImageFont

from lib.colors import facility_color
from lib.static_map import render_static_map

logger = logging.getLogger(__name__)

# --- Canvas geometry (SPEC §8.3) -------------------------------------------
CANVAS_W = 1280
CANVAS_H = 720

HEADER_H = 64               # purple band (0..64)
METRIC_H = 40               # "対象推進園数 N件" strip (64..104)
MAP_TOP = HEADER_H + METRIC_H  # 104
MAP_W = 656                 # map area width
MAP_H = CANVAS_H - MAP_TOP  # 616 (map area height, top-left (0, MAP_TOP))

LIST_X = MAP_W             # facility list left edge (656)
LIST_W = CANVAS_W - LIST_X  # 624
LIST_HEADER_H = 40          # "施設リスト" band (104..144)
LIST_TOP = MAP_TOP + LIST_HEADER_H  # 144
CARD_H = 56                 # card height per facility

# --- Colors ----------------------------------------------------------------
PURPLE = "#7C3AED"
WHITE = "#FFFFFF"
NAME_COLOR = "#111827"
DIST_COLOR = "#6B7280"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E5E7EB"

# --- Font ------------------------------------------------------------------
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "ipaexg.ttf")
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Return a cached IPAexGothic font at *size*."""
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(_FONT_PATH, size)
    return _font_cache[size]


def compose_canvas(
    map_png_bytes: bytes, store_row, facilities_df, radius_km: float
) -> bytes:
    """
    Compose the 1280x720 deliverable PNG (SPEC §8.3).

    Pure function: the map is supplied as PNG bytes, so this can be tested
    locally with a placeholder image (no browser required).

    Layout
    ------
    - Header band 0..64        : purple, white 22px bold, left pad 24, v-center
    - Metric strip 64..104     : white, "対象推進園数 N件" (matches the on-screen
                                 st.metric placed between band and map)
    - Map area 0..656 x 104..720 : map PNG resized to 656x616
    - List area 656..1280 x 104..720
        * 104..144 purple band : centered "施設リスト"
        * cards 56px each      : badge + name + distance + bottom rule
        * overflow             : trailing "他 N 件"
    """
    store_name = store_row["店舗名称"]

    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), WHITE)
    draw = ImageDraw.Draw(canvas)

    # --- Header band ---
    draw.rectangle([0, 0, CANVAS_W, HEADER_H], fill=PURPLE)
    header_text = f"{store_name} 周辺マップ概要 ｜ 半径{radius_km}km圏内"
    draw.text(
        (24, HEADER_H / 2),
        header_text,
        font=_font(22),
        fill=WHITE,
        anchor="lm",
        stroke_width=1,          # simulate bold (IPAexGothic has no bold face)
        stroke_fill=WHITE,
    )

    # --- Metric strip (between band and map, mirrors on-screen st.metric) ---
    n = len(facilities_df)
    metric_cy = HEADER_H + METRIC_H / 2
    draw.text(
        (24, metric_cy),
        "対象推進園数",
        font=_font(12),
        fill=DIST_COLOR,
        anchor="lm",
    )
    label_w = draw.textlength("対象推進園数", font=_font(12))
    draw.text(
        (24 + label_w + 12, metric_cy),
        f"{n}件",
        font=_font(20),
        fill=NAME_COLOR,
        anchor="lm",
        stroke_width=1,
        stroke_fill=NAME_COLOR,
    )

    # --- Map area (656x616, top-left at (0, MAP_TOP)) ---
    map_img = Image.open(io.BytesIO(map_png_bytes)).convert("RGB")
    map_img = map_img.resize((MAP_W, MAP_H))
    canvas.paste(map_img, (0, MAP_TOP))

    # --- List header band ("施設リスト") ---
    draw.rectangle([LIST_X, MAP_TOP, CANVAS_W, LIST_TOP], fill=PURPLE)
    draw.text(
        (LIST_X + LIST_W / 2, MAP_TOP + LIST_HEADER_H / 2),
        "施設リスト",
        font=_font(16),
        fill=WHITE,
        anchor="mm",
        stroke_width=1,
        stroke_fill=WHITE,
    )

    # --- Facility cards ---
    total = len(facilities_df)
    list_height = CANVAS_H - LIST_TOP            # 576
    max_cards = list_height // CARD_H            # 10

    if total <= max_cards:
        draw_count = total
        overflow = 0
    else:
        # reserve the last slot for the "他 N 件" line
        draw_count = max_cards - 1
        overflow = total - draw_count

    badge_r = 12
    badge_cx = LIST_X + 16 + badge_r            # left margin 16, radius 12
    text_x = LIST_X + 16 + badge_r * 2 + 12     # badge right edge + 12 gap

    name_font = _font(14)
    dist_font = _font(12)
    badge_font = _font(12)

    for i in range(draw_count):
        row = facilities_df.iloc[i]
        top = LIST_TOP + i * CARD_H
        cy = top + CARD_H / 2

        color = facility_color(row["推進園区分"])
        number = int(row["連番"])

        # number badge (filled circle)
        draw.ellipse(
            [badge_cx - badge_r, cy - badge_r, badge_cx + badge_r, cy + badge_r],
            fill=color,
        )
        draw.text(
            (badge_cx, cy),
            str(number),
            font=badge_font,
            fill=WHITE,
            anchor="mm",
        )

        # facility name (bold) + distance (muted)
        name = str(row["推進園名称"])
        distance_text = f"約{row['距離km']:.2f}km"
        draw.text(
            (text_x, cy - 9),
            name,
            font=name_font,
            fill=NAME_COLOR,
            anchor="lm",
            stroke_width=1,
            stroke_fill=NAME_COLOR,
        )
        draw.text(
            (text_x, cy + 11),
            distance_text,
            font=dist_font,
            fill=DIST_COLOR,
            anchor="lm",
        )

        # bottom rule
        rule_y = top + CARD_H - 1
        draw.line([LIST_X, rule_y, CANVAS_W, rule_y], fill=CARD_BORDER, width=1)

    if overflow > 0:
        top = LIST_TOP + draw_count * CARD_H
        cy = top + CARD_H / 2
        draw.text(
            (text_x, cy),
            f"他 {overflow} 件",
            font=name_font,
            fill=DIST_COLOR,
            anchor="lm",
        )

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def build_png(store_row, facilities_df, radius_km: float) -> bytes:
    """
    Build the composite PNG for one store (SPEC §8.3 full path).

    Renders the map browserlessly (pure-Python OSM tiles via lib.static_map),
    then composes the canvas.  Exceptions propagate so callers can skip
    failing stores (SPEC §11).
    """
    map_png = render_static_map(store_row, facilities_df, radius_km)
    return compose_canvas(map_png, store_row, facilities_df, radius_km)
