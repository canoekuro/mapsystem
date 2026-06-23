"""
PNG composition for mapsystem (SPEC §8.3).

The downloaded PNG is a single 1280x720 image combining the purple header
band, the folium map, and the facility list.  folium's native ``_to_png``
only renders the map area, so the rest is composed with Pillow.

Design
------
Acquisition and composition are kept separate so the (hard to run) headless
browser step is isolated and the composition is a pure, locally testable
function:

    _map_to_png(m)              -- folium.Map -> map-only PNG bytes (selenium)
    compose_canvas(map_png, ..) -- pure: map PNG bytes -> composite PNG bytes
    build_png(...)             -- _map_to_png(build_map(...)) -> compose_canvas
"""

import io
import logging
import os
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont

from lib.map_builder import build_map

logger = logging.getLogger(__name__)

# --- Canvas geometry (SPEC §8.3) -------------------------------------------
CANVAS_W = 1280
CANVAS_H = 720

HEADER_H = 64               # purple band height
MAP_SIZE = 656             # map area is 656 x 656, top-left (0, HEADER_H)

LIST_X = MAP_SIZE          # facility list left edge (656)
LIST_W = CANVAS_W - LIST_X  # 624
LIST_HEADER_H = 40          # "施設リスト" band (64..104)
LIST_TOP = HEADER_H + LIST_HEADER_H  # 104
CARD_H = 56                 # card height per facility

# --- Colors ----------------------------------------------------------------
PURPLE = "#7C3AED"
WHITE = "#FFFFFF"
NAME_COLOR = "#111827"
DIST_COLOR = "#6B7280"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E5E7EB"

_FACILITY_COLORS = {
    "保育園": "#22C55E",
    "幼稚園": "#EF4444",
    "こども園": "#F59E0B",
}
_FALLBACK_COLOR = "#6B7280"

# --- Font ------------------------------------------------------------------
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "ipaexg.ttf")
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Return a cached IPAexGothic font at *size*."""
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(_FONT_PATH, size)
    return _font_cache[size]


def _map_to_png(m, delay: int = 3) -> bytes:
    """
    Render *m* (folium.Map) to a map-only PNG using headless Chrome.

    Uses selenium directly (selenium 4 Selenium Manager resolves the driver)
    with container-safe Chrome flags.  Requires a Chrome/Chromium binary and
    network access to the tile host; on Databricks Apps these come from
    app.yaml.  Exceptions propagate to the caller (SPEC §11).
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    html = m.get_root().render()
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--window-size=720,620")

    driver = webdriver.Chrome(options=opts)
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        driver.get("file://" + path)
        time.sleep(delay)
        return driver.get_screenshot_as_png()
    finally:
        driver.quit()
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def compose_canvas(
    map_png_bytes: bytes, store_row, facilities_df, radius_km: float
) -> bytes:
    """
    Compose the 1280x720 deliverable PNG (SPEC §8.3).

    Pure function: the map is supplied as PNG bytes, so this can be tested
    locally with a placeholder image (no browser required).

    Layout
    ------
    - Header band 0..64       : purple, white 22px bold, left pad 24, v-center
    - Map area 0..656 x 64..720 : map PNG resized to 656x656
    - List area 656..1280 x 64..720
        * 64..104 purple band  : centered "施設リスト"
        * cards 56px each      : badge + name + distance + bottom rule
        * overflow             : trailing "他 N 件"
    """
    store_name = store_row["小売店名称"]

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

    # --- Map area (656x656, top-left at (0, HEADER_H)) ---
    map_img = Image.open(io.BytesIO(map_png_bytes)).convert("RGB")
    map_img = map_img.resize((MAP_SIZE, MAP_SIZE))
    canvas.paste(map_img, (0, HEADER_H))

    # --- List header band ("施設リスト") ---
    draw.rectangle([LIST_X, HEADER_H, CANVAS_W, LIST_TOP], fill=PURPLE)
    draw.text(
        (LIST_X + LIST_W / 2, HEADER_H + LIST_HEADER_H / 2),
        "施設リスト",
        font=_font(16),
        fill=WHITE,
        anchor="mm",
        stroke_width=1,
        stroke_fill=WHITE,
    )

    # --- Facility cards ---
    total = len(facilities_df)
    list_height = CANVAS_H - LIST_TOP            # 616
    max_cards = list_height // CARD_H            # 11

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

        color = _FACILITY_COLORS.get(row["施設区分"], _FALLBACK_COLOR)
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
        name = str(row["施設名称"])
        distance_text = f"約{row['距離']}km"
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

    Renders the folium map via headless Chrome, then composes the canvas.
    Exceptions propagate so callers can skip failing stores (SPEC §11).
    """
    m = build_map(store_row, facilities_df, radius_km)
    map_png = _map_to_png(m)
    return compose_canvas(map_png, store_row, facilities_df, radius_km)
