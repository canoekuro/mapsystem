"""
Browserless static map rendering (SPEC §8.3 map area).

Databricks Apps has no root access and cannot install a browser, so the
selenium/headless-Chrome path used by folium ``_to_png`` cannot run there.
This module renders the map image with pure Python instead: it fetches OSM
slippy tiles over HTTP, stitches them with Pillow, and draws the radius
circle, the store marker, numbered facility markers, and the legend using a
Web Mercator projection.

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

from lib.data import zoom_for_radius

logger = logging.getLogger(__name__)

TILE_SIZE = 256
_EARTH_RADIUS_KM = 6371.0

# Tile source / identification (overridable for egress-restricted workspaces).
_TILE_URL = os.getenv("OSM_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
_USER_AGENT = os.getenv(
    "MAP_TILE_USER_AGENT", "mapsystem/1.0 (+https://github.com/canoekuro/mapsystem)"
)
_TILE_TIMEOUT = float(os.getenv("MAP_TILE_TIMEOUT", "15"))

# Colors (shared with png_builder / map_builder; SPEC §6.1.2)
_PURPLE = (124, 58, 237)            # #7C3AED
_WHITE = (255, 255, 255)
_FACILITY_COLORS = {
    "保育園": (34, 197, 94),        # #22C55E
    "幼稚園": (239, 68, 68),        # #EF4444
    "こども園": (245, 158, 11),     # #F59E0B
}
_FALLBACK_COLOR = (107, 114, 128)   # #6B7280
_STORE_COLOR = (17, 24, 39)         # near-black

# Font (IPAexGothic, same file png_builder uses)
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "ipaexg.ttf")


@lru_cache(maxsize=64)
def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size)


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
def _fetch_tile(z: int, x: int, y: int) -> bytes:
    """Fetch a single OSM tile (cached across calls to dedupe bulk runs)."""
    url = _TILE_URL.format(z=z, x=x, y=y)
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TILE_TIMEOUT)
    resp.raise_for_status()
    return resp.content


# --- Rendering --------------------------------------------------------------

def render_static_map(store_row, facilities_df, radius_km: float, size: int = 656) -> bytes:
    """
    Render a size x size PNG centered on the store (SPEC §6.1.2 map area).

    Draws OSM base tiles, the radius circle, the store marker, numbered
    facility markers (colored by 施設区分), and a legend.  Tile-fetch failures
    propagate so callers can skip the store (SPEC §11).
    """
    clat = float(store_row["店舗緯度"])
    clon = float(store_row["店舗経度"])
    zoom = zoom_for_radius(radius_km, clat, viewport_px=size)
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
            tile_bytes = _fetch_tile(zoom, txw, ty)
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

    # --- Radius circle (geodesic polygon, translucent fill) ---
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    ring = [to_px(*_destination_point(clat, clon, b * 5, radius_km)) for b in range(72)]
    odraw.polygon(ring, fill=(*_PURPLE, 20), outline=(*_PURPLE, 255))
    # thicken the outline a touch
    odraw.line(ring + [ring[0]], fill=(*_PURPLE, 255), width=2)
    base = Image.alpha_composite(base, overlay)

    draw = ImageDraw.Draw(base)

    # --- Facility markers (colored circle + white number) ---
    badge_font = _font(12)
    for _, row in facilities_df.iterrows():
        px, py = to_px(float(row["施設緯度"]), float(row["施設経度"]))
        color = _FACILITY_COLORS.get(row["施設区分"], _FALLBACK_COLOR)
        r = 11
        draw.ellipse(
            [px - r, py - r, px + r, py + r],
            fill=(*color, 255),
            outline=(*_WHITE, 255),
            width=2,
        )
        draw.text((px, py), str(int(row["連番"])), font=badge_font, fill=(*_WHITE, 255), anchor="mm")

    # --- Store marker (distinct dark marker at center) ---
    sx, sy = to_px(clat, clon)
    sr = 12
    draw.ellipse(
        [sx - sr, sy - sr, sx + sr, sy + sr],
        fill=(*_STORE_COLOR, 255),
        outline=(*_WHITE, 255),
        width=3,
    )
    draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=(*_WHITE, 255))

    # --- Legend (bottom-right) ---
    _draw_legend(base)

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def _draw_legend(img: Image.Image) -> None:
    """Draw the facility-type legend in the bottom-right corner."""
    draw = ImageDraw.Draw(img)
    font = _font(13)
    items = [("保育園", _FACILITY_COLORS["保育園"]),
             ("幼稚園", _FACILITY_COLORS["幼稚園"]),
             ("こども園", _FACILITY_COLORS["こども園"])]
    pad = 8
    line_h = 20
    dot_r = 6
    box_w = 96
    box_h = pad * 2 + line_h * len(items)
    x0 = img.width - box_w - 10
    y0 = img.height - box_h - 10
    draw.rectangle(
        [x0, y0, x0 + box_w, y0 + box_h],
        fill=(*_WHITE, 235),
        outline=(*_FALLBACK_COLOR, 255),
    )
    for i, (label, color) in enumerate(items):
        cy = y0 + pad + line_h * i + line_h / 2
        cx = x0 + pad + dot_r
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(*color, 255))
        draw.text((cx + dot_r + 6, cy), label, font=font, fill=(*_STORE_COLOR, 255), anchor="lm")
