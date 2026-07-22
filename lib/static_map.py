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
render_static_map(store_row, facilities_df, radius_km, width=656, height=656) -> bytes
"""

import io
import logging
import math
import os
from functools import lru_cache

import requests
from PIL import Image, ImageDraw, ImageFont

from lib import icons
from lib.basemaps import get_basemap
from lib.colors import (
    basemap_id,
    circle_color_rgb,
    circle_fill_opacity,
    facility_color_rgb,
    facility_marker_size_for_radius,
    store_marker_size,
)
from lib.data import zoom_for_radius

logger = logging.getLogger(__name__)

TILE_SIZE = 256
_EARTH_RADIUS_KM = 6371.0

# 情報粒度（タイル取得ズーム）の上限。表示ズームがこれを超えても取得は 14 で頭打ちにし、
# 14 相当タイルを拡大して用いる（対話地図の max_native_zoom と同挙動、SPEC §6.1.2 追補）。
_DETAIL_ZOOM_CAP = 14

# タイルURLは選択中のベースマップ（lib.basemaps / テーマ）から決まる。
# OSM_TILE_URL 環境変数が設定されていれば、egress 制限ワークスペース向けにそれを優先する。
_TILE_URL_OVERRIDE = os.getenv("OSM_TILE_URL") or None
_USER_AGENT = os.getenv(
    "MAP_TILE_USER_AGENT", "mapsystem/1.0 (+https://github.com/canoekuro/mapsystem)"
)
_TILE_TIMEOUT = float(os.getenv("MAP_TILE_TIMEOUT", "15"))

# Colors: 推進園区分・半径円・店舗マーカーは lib.colors（テーマ）から取得する（SPEC §6.1.2）。
_WHITE = (255, 255, 255)
_ATTR_BG = (255, 255, 255)
_ATTR_TEXT = (75, 85, 99)           # #4B5563

# Font (IPAexGothic, same file png_builder uses)
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "ipaexg.ttf")


@lru_cache(maxsize=64)
def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONT_PATH, size)


def _draw_attribution(draw: ImageDraw.ImageDraw, width: int, height: int, text: str) -> None:
    """タイル提供元の帰属表示を地図右下に描画する（OSM/GSI/CARTO とも必須）。"""
    font = _font(11)
    pad = 4
    tw = draw.textlength(text, font=font)
    th = 13
    x1 = width - 6
    y1 = height - 6
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

def render_static_map(
    store_row,
    facilities_df,
    radius_km: float,
    width: int = 656,
    height: int = 656,
) -> bytes:
    """
    Render a *width* x *height* PNG centered on the store (SPEC §6.1.2 map area).

    Draws OSM base tiles, the radius circle, the store marker, and numbered
    facility markers.  Tile-fetch failures propagate so callers can skip the
    store (SPEC §11).

    寸法は既定で正方（656×656）だが、対話地図（``lib.map_builder.build_map`` の
    ``map_width×map_height``）と体裁を合わせるため width/height を個別指定できる。
    表示ズームは対話地図と同じく縦の見付（height）を基準に算出する（issue 202607221245）。
    """
    clat = float(store_row["店舗lat"])
    clon = float(store_row["店舗lon"])
    bm = get_basemap(basemap_id())
    tile_url = _TILE_URL_OVERRIDE or bm["url"]

    # 表示ズーム（半径円が枠内に収まるズーム）と、タイル取得ズーム（情報粒度）を分離する。
    # 粒度が 15 以上になるときは 14 で頭打ちにし、14 相当タイルを scale 倍に拡大して用いる。
    # PNG では取得ズームを抑えるだけで枠取り（表示ズーム）は維持する（SPEC §6.1.2 追補）。
    # 対話地図 build_map と一致させるため viewport は縦（height）を用いる。
    z_display = zoom_for_radius(radius_km, clat, viewport_px=height, max_zoom=bm["max_zoom"])
    z_native = min(z_display, _DETAIL_ZOOM_CAP)
    scale = 2 ** (z_display - z_native)  # 1, 2, 4, ...（14 以下なら 1＝従来通り）
    n_tiles = 2 ** z_native

    # 表示（z_display）グローバル画素での窓。オーバーレイ（円・マーカー）に使う。
    cxd, cyd = _project(clat, clon, z_display)
    left = cxd - width / 2.0
    top = cyd - height / 2.0

    # 取得（z_native）グローバル画素での窓。scale で表示窓と厳密対応する（left = scale * left_n）。
    native_w = width / scale
    native_h = height / scale
    cxn, cyn = _project(clat, clon, z_native)
    left_n = cxn - native_w / 2.0
    top_n = cyn - native_h / 2.0
    right_n = cxn + native_w / 2.0
    bottom_n = cyn + native_h / 2.0

    # 取得窓を覆う整数の native 画素ボックス（拡大後に表示窓を正確に切り出せるよう 1px 余白）。
    nx0 = math.floor(left_n) - 1
    ny0 = math.floor(top_n) - 1
    nx1 = math.ceil(right_n) + 1
    ny1 = math.ceil(bottom_n) + 1

    x_min = math.floor(nx0 / TILE_SIZE)
    x_max = math.floor((nx1 - 1) / TILE_SIZE)
    y_min = math.floor(ny0 / TILE_SIZE)
    y_max = math.floor((ny1 - 1) / TILE_SIZE)

    mosaic_w = (x_max - x_min + 1) * TILE_SIZE
    mosaic_h = (y_max - y_min + 1) * TILE_SIZE
    mosaic = Image.new("RGB", (mosaic_w, mosaic_h), (229, 231, 235))

    for tx in range(x_min, x_max + 1):
        for ty in range(y_min, y_max + 1):
            if ty < 0 or ty >= n_tiles:
                continue  # above/below the world — leave background
            txw = tx % n_tiles  # wrap longitude
            tile_bytes = _fetch_tile(z_native, txw, ty, tile_url)
            tile_img = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
            mosaic.paste(
                tile_img,
                ((tx - x_min) * TILE_SIZE, (ty - y_min) * TILE_SIZE),
            )

    # native ボックスを切り出し → scale 倍に拡大 → 表示窓（size×size）を厳密に切り出す。
    sub = mosaic.crop(
        (nx0 - x_min * TILE_SIZE, ny0 - y_min * TILE_SIZE,
         nx1 - x_min * TILE_SIZE, ny1 - y_min * TILE_SIZE)
    )
    if scale != 1:
        sub = sub.resize(((nx1 - nx0) * scale, (ny1 - ny0) * scale))
    off_x = int(round(left - nx0 * scale))
    off_y = int(round(top - ny0 * scale))
    base = sub.crop((off_x, off_y, off_x + width, off_y + height)).convert("RGBA")

    def to_px(lat: float, lon: float) -> tuple[float, float]:
        gx, gy = _project(lat, lon, z_display)
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

    # --- Facility markers (colored circle + white number; サイズは地図半径ごとにテーマ調整可) ---
    fac_scale = facility_marker_size_for_radius(radius_km)
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

    # --- Store marker (images/icon.png ピン、tip を店舗座標へ合わせる; サイズはテーマ調整可) ---
    store_w, store_h = icons.store_icon_size(store_marker_size())
    tip_rx, tip_ry = icons.store_icon_tip()
    sx, sy = to_px(clat, clon)
    with Image.open(icons.icon_path()) as _icon:
        icon_img = _icon.convert("RGBA").resize((store_w, store_h))
    base.paste(
        icon_img,
        (round(sx - store_w * tip_rx), round(sy - store_h * tip_ry)),
        icon_img,
    )

    # 凡例は廃止（区分色分けをやめ単一色で描画するため, issue 202607161811）。

    # --- Tile attribution (提供元の帰属表示、右下) ---
    _draw_attribution(draw, width, height, bm["attribution"])

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG")
    return out.getvalue()
