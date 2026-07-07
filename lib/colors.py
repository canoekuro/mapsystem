"""
推進園区分の色定義（SPEC §6.1.2）。

地図（folium）・ダウンロードPNG・静的PNG・施設リストで共有する唯一の色定義。
ここを変更すれば全描画に反映される（旧来は各モジュールに重複定義され、実データの
区分名変更時に一部だけが取り残される不具合の温床だった）。

``FACILITY_COLORS`` の定義順は凡例の表示順を兼ねる。
"""

# 推進園区分 -> 背景色（16進 "#RRGGBB"）。
# 認可保育所/認定こども園 が紛らわしいという指摘を受け、色覚多様性にも配慮した
# 高コントラストな3色（青/橙/紫）へ変更。紛らわしかった2区分（認可保育所・認定こども園）は
# 最も離れた色対（青↔橙）に割り当てている。白抜き番号が読めるよう各色は十分に濃い。
# 色の分離は dataviz スキルの validate_palette で検証済み（隣接CVD ΔE ≥ 16.6, 目標12以上）。
FACILITY_COLORS: dict[str, str] = {
    "認可保育所": "#2A78D6",   # 青
    "認定こども園": "#EB6834",  # 橙
    "幼稚園": "#4A3AA7",       # 紫
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
