"""
店舗マーカーの画像アイコン（``images/icon.png``）の単一の入口。

対話地図（``lib/map_builder.py`` の folium）とダウンロードPNG（``lib/static_map.py`` の
Pillow）で、同じアイコン画像・同じ先端（tip）位置を共有するための小さなヘルパー。

アイコンはピン型（下端が尖ったマーカー形状）で、周囲に透明余白を含む。マーカーを地図座標へ
正しく合わせるため、不透明領域の下端中央＝ピン先端を ``getbbox()`` から比率で求め、両描画経路
で共通のアンカーとして使う。

Public API
----------
icon_path()               -- images/icon.png の絶対パス
store_icon_tip()          -- ピン先端の (rx, ry) 比率（0.0–1.0）
store_icon_size(scale_pct) -- 相対サイズ（％）から (width, height) px を算出
"""

import os
from functools import lru_cache

from PIL import Image

# アイコンの原寸アスペクト（480:720 = 2:3）。基準高からこの比で幅を決める。
_ICON_W = 480
_ICON_H = 720

# 100％時の店舗アイコン高（px）。store_marker_size（％）を掛けて実サイズを得る。
# ピン型のため従来のカート BeautifyIcon（約30px 角）よりやや縦長にする。
_STORE_ICON_BASE_H = 42

_ICON_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "images", "icon.png")
)


def icon_path() -> str:
    """店舗アイコン ``images/icon.png`` の絶対パス。"""
    return _ICON_PATH


@lru_cache(maxsize=1)
def store_icon_tip() -> tuple[float, float]:
    """
    ピン先端（下端中央）の位置を画像サイズに対する比率 ``(rx, ry)`` で返す。

    ``getbbox()`` で不透明領域の境界 ``(l, t, r, b)`` を取り、先端 x = 左右中央、
    先端 y = 下端とする。透明余白を吸収するので、リサイズ後も先端を地図座標へ合わせられる。
    """
    with Image.open(_ICON_PATH) as img:
        width, height = img.size
        bbox = img.getbbox()
    if not bbox:
        return 0.5, 1.0
    left, _top, right, bottom = bbox
    return (left + right) / 2 / width, bottom / height


def store_icon_size(scale_pct: int) -> tuple[int, int]:
    """相対サイズ ``scale_pct``（％、100=既定）から ``(width, height)`` px を返す。"""
    height = max(1, round(_STORE_ICON_BASE_H * scale_pct / 100))
    width = max(1, round(height * _ICON_W / _ICON_H))
    return width, height
