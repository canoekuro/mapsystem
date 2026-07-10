"""
Browserless static map rendering (SPEC §8.3 map area).

Databricks Apps has no root access and cannot install a browser, so the
selenium/headless-Chrome path used by folium ``_to_png`` cannot run there.
This module renders the map image with pure Python instead: it fetches OSM
slippy tiles over HTTP, stitches them with Pillow, and draws the radius
circle, the store marker, and numbered facility markers using a Web Mercator
projection.

Dependencies are only Pillow + requests (already in the dependency tree), so
no browser and no extra heavy package — container start stays fast.

Public API
----------
render_static_map(store_row, facilities_df, radius_km, size=656) -> bytes
"""

import io
import logging
import math
import os
from functools import lru_cache

import requests
from PIL import Image, ImageDraw, ImageFont

from lib.basemaps import get_basemap
from lib.colors import (
    basemap_id,
    circle_color_rgb,
    circle_fill_opacity,
    facility_color_rgb,
    facility_colors,
    facility_marker_size,
    hex_to_rgb,
    store_marker_color_rgb,
    store_marker_size,
)
from lib.data import zoom_for_radius

logger = logging.getLogger(__name__)

TILE_SIZE = 256
_EARTH_RADIUS_KM = 6371.0

# タイルURLは選択中のベースマップ（lib.basemaps / テーマ）から決まる。
# OSM_TILE_URL 環境変数が設定されていれば、egress 制限ワークスペース向けにそれを優先する。
_TILE_URL_OVERRIDE = os.getenv("OSM_TILE_URL") or None
_USER_AGENT = os.getenv(
    "MAP_TILE_USER_AGENT", "mapsystem/1.0 (+https://github.com/canoekuro/mapsystem)"
)
_TILE_TIMEOUT = float(os.getenv("MAP_TILE_TIMEOUT", "15"))

# Colors: 推進園区分・半径円・店舗マーカーは lib.colors（テーマ）から取得する（SPEC §6.1.2）。
_WHITE = (255, 255, 255)
_LEGEND_BG = (255, 255, 255)
_LEGEND_BORDER = (229, 231, 235)    # #E5E7EB
_LEGEND_TEXT = (17, 24, 39)         # #111827
_ATTR_BG = (255, 255, 255)
_ATTR_TEXT = (75, 85, 99)           # #4B5563

# Font (IPAexGothic, same file png_builder uses)
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "ipaexg.ttf")


@lru_cache(maxsize=64)
def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size)


def _draw_legend(draw: ImageDraw.ImageDraw, size: int) -> None:
    """推進園区分の凡例を地図左下に描画する（SPEC §6.1.2、baked into the PNG）。"""
    title_font = _font(13)
    item_font = _font(12)

    pad = 8
    row_h = 18
    dot_r = 6
    title_h = 18
    items = list(facility_colors().items())

    text_w = max(draw.textlength(cat, font=item_font) for cat, _ in items)
    title_w = draw.textlength("推進園区分", font=title_font)
    box_w = int(pad * 2 + dot_r * 2 + 6 + max(text_w, title_w))
    box_h = pad * 2 + title_h + row_h * len(items)

    x0 = 12
    y1 = size - 12
    y0 = y1 - box_h
    x1 = x0 + box_w

    draw.rounded_rectangle(
        [x0, y0, x1, y1], radius=6, fill=_LEGEND_BG, outline=_LEGEND_BORDER, width=1
    )
    draw.text((x0 + pad, y0 + pad), "推進園区分", font=title_font, fill=_LEGEND_TEXT, anchor="lt")

    for i, (category, hex_color) in enumerate(items):
        cy = y0 + pad + title_h + row_h * i + row_h / 2
        dot_cx = x0 + pad + dot_r
        draw.ellipse(
            [dot_cx - dot_r, cy - dot_r, dot_cx + dot_r, cy + dot_r],
            fill=hex_to_rgb(hex_color),
        )
        draw.text(
            (dot_cx + dot_r + 6, cy), category, font=item_font, fill=_LEGEND_TEXT, anchor="lm"
        )


def _draw_attribution(draw: ImageDraw.ImageDraw, size: int, text: str) -> None:
    """タイル提供元の帰属表示を地図右下に描画する（OSM/GSI/CARTO とも必須）。"""
    font = _font(11)
    pad = 4
    tw = draw.textlength(text, font=font)
    th = 13
    x1 = size - 6
    y1 = size - 6
    x0 = x1 - tw - pad * 2
    y0 = y1 - th - pad * 2
    draw.rectangle([x0, y0, x1, y1], fill=_ATTR_BG)
    draw.text((x0 + pad, y0 + pad), text, font=font, fill=_ATTR_TEXT, anchor="lt")


# --- Web Mercator projection ------------------------------------------------

def _project(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Return global pixel coordinates (x, y) for lat/lon at *zoom*."""
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def _destination_point(lat: float, lon: float, bearing_deg: float, dist_km: float):
    """Great-circle destination point from (lat, lon)."""
    delta = dist_km / _EARTH_RADIUS_KM
    theta = math.radians(bearing_deg)
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta)
        + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lam2 = lam1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), math.degrees(lam2)


# --- Tile fetching ----------------------------------------------------------

@lru_cache(maxsize=2048)
def _fetch_tile(z: int, x: int, y: int, url_template: str) -> bytes:
    """Fetch a single raster tile (cached; keyed on url_template to avoid mixing basemaps)."""
    url = url_template.format(z=z, x=x, y=y)
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TILE_TIMEOUT)
    resp.raise_for_status()
    return resp.content


# --- Rendering --------------------------------------------------------------

def render_static_map(store_row, facilities_df, radius_km: float, size: int = 656) -> bytes:
    """
    Render a size x size PNG centered on the store (SPEC §6.1.2 map area).

    Draws OSM base tiles, the radius circle, the store marker, and numbered
    facility markers.  Tile-fetch failures propagate so callers can skip the
    store (SPEC §11).
    """
    clat = float(store_row["店舗lat"])
    clon = float(store_row["店舗lon"])
    bm = get_basemap(basemap_id())
    tile_url = _TILE_URL_OVERRIDE or bm["url"]
    zoom = zoom_for_radius(radius_km, clat, viewport_px=size, max_zoom=bm["max_zoom"])
    n_tiles = 2 ** zoom

    cx, cy = _project(clat, clon, zoom)
    left = cx - size / 2.0
    top = cy - size / 2.0
    right = cx + size / 2.0
    bottom = cy + size / 2.0

    x_min = math.floor(left / TILE_SIZE)
    x_max = math.floor((right - 1) / TILE_SIZE)
    y_min = math.floor(top / TILE_SIZE)
    y_max = math.floor((bottom - 1) / TILE_SIZE)

    mosaic_w = (x_max - x_min + 1) * TILE_SIZE
    mosaic_h = (y_max - y_min + 1) * TILE_SIZE
    mosaic = Image.new("RGB", (mosaic_w, mosaic_h), (229, 231, 235))

    for tx in range(x_min, x_max + 1):
        for ty in range(y_min, y_max + 1):
            if ty < 0 or ty >= n_tiles:
                continue  # above/below the world — leave background
            txw = tx % n_tiles  # wrap longitude
            tile_bytes = _fetch_tile(zoom, txw, ty, tile_url)
            tile_img = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
            mosaic.paste(
                tile_img,
                ((tx - x_min) * TILE_SIZE, (ty - y_min) * TILE_SIZE),
            )

    # Crop the mosaic to the size x size window centered on the store.
    off_x = int(round(left - x_min * TILE_SIZE))
    off_y = int(round(top - y_min * TILE_SIZE))
    base = mosaic.crop((off_x, off_y, off_x + size, off_y + size)).convert("RGBA")

    def to_px(lat: float, lon: float) -> tuple[float, float]:
        gx, gy = _project(lat, lon, zoom)
        return gx - left, gy - top

    # --- Radius circle (geodesic polygon, translucent fill; テーマ調整可) ---
    circle_rgb = circle_color_rgb()
    fill_alpha = int(round(circle_fill_opacity() * 255))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    ring = [to_px(*_destination_point(clat, clon, b * 5, radius_km)) for b in range(72)]
    odraw.polygon(ring, fill=(*circle_rgb, fill_alpha), outline=(*circle_rgb, 255))
    # thicken the outline a touch
    odraw.line(ring + [ring[0]], fill=(*circle_rgb, 255), width=2)
    base = Image.alpha_composite(base, overlay)

    draw = ImageDraw.Draw(base)

    # --- Facility markers (colored circle + white number; サイズはテーマ調整可) ---
    fac_scale = facility_marker_size()
    r = max(3, round(11 * fac_scale / 100))
    badge_font = _font(max(6, round(12 * fac_scale / 100)))
    for _, row in facilities_df.iterrows():
        px, py = to_px(float(row["推進園lat"]), float(row["推進園lon"]))
        color = facility_color_rgb(row["推進園区分"])
        draw.ellipse(
            [px - r, py - r, px + r, py + r],
            fill=(*color, 255),
            outline=(*_WHITE, 255),
            width=2,
        )
        draw.text((px, py), str(int(row["連番"])), font=badge_font, fill=(*_WHITE, 255), anchor="mm")

    # --- Store marker (distinct marker at center; サイズ・色ともテーマ調整可) ---
    store_rgb = store_marker_color_rgb()
    store_scale = store_marker_size()
    sx, sy = to_px(clat, clon)
    sr = max(4, round(12 * store_scale / 100))
    inner_r = max(1, round(3 * store_scale / 100))
    draw.ellipse(
        [sx - sr, sy - sr, sx + sr, sy + sr],
        fill=(*store_rgb, 255),
        outline=(*_WHITE, 255),
        width=3,
    )
    draw.ellipse([sx - inner_r, sy - inner_r, sx + inner_r, sy + inner_r], fill=(*_WHITE, 255))

    # --- Legend (推進園区分の色分け凡例) ---
    _draw_legend(draw, size)

    # --- Tile attribution (提供元の帰属表示、右下) ---
    _draw_attribution(draw, size, bm["attribution"])

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG")
    return out.getvalue()
