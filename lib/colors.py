"""
推進園区分の色定義（SPEC §6.1.2）。

地図（folium）・ダウンロードPNG・静的PNG・施設リストで共有する唯一の色定義。
ここを変更すれば全描画に反映される（旧来は各モジュールに重複定義され、実データの
区分名変更時に一部だけが取り残される不具合の温床だった）。

``FACILITY_COLORS`` の定義順は凡例の表示順を兼ねる。
"""

# 推進園区分 -> 背景色（16進 "#RRGGBB"）。
FACILITY_COLORS: dict[str, str] = {
    "認可保育所": "#22C55E",   # 緑
    "認定こども園": "#F59E0B",  # 黄
    "幼稚園": "#EF4444",       # 赤
}

# 想定外 / 区分なしのフォールバック色（灰）。
FALLBACK_COLOR = "#6B7280"


def facility_color(category: str) -> str:
    """推進園区分に対応する16進色を返す（未知値はフォールバック色）。"""
    return FACILITY_COLORS.get(category, FALLBACK_COLOR)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """``"#RRGGBB"`` を ``(R, G, B)`` タプルへ変換する。"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def facility_color_rgb(category: str) -> tuple[int, int, int]:
    """推進園区分に対応する ``(R, G, B)`` タプルを返す（未知値はフォールバック色）。"""
    return hex_to_rgb(facility_color(category))
