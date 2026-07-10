"""
配色テーマの単一の入口（SPEC §6.1.2 / §8.3）。

地図（folium）・ダウンロードPNG・静的PNG・施設リスト・凡例で共有する唯一の色定義。
値は ``config/theme.toml`` の ``[theme]`` / ``[theme.facility_colors]`` から読み込み、
未設定・不正時は組み込み既定（``_DEFAULTS``）へフォールバックする。
「テーマ設定」ページ（views/config_page.py）がこのファイルを書き換えて配色を調整する。

**描画時に解決すること**が肝で、各アクセサは import 時の定数ではなく関数として提供する
（保存やプレビュー反映後の再描画で最新テーマが反映されるようにするため）。

Public API
----------
facility_colors() / facility_color(cat) / facility_color_rgb(cat)
circle_color() / circle_color_rgb() / circle_fill_opacity()
band_color() / band_color_rgb()
store_marker_color() / store_marker_color_rgb()
basemap_id()
map_width() / map_height() / map_detail_zoom()
hex_to_rgb(hex)
get_theme() / reload_theme() / apply_overrides(values)
save_theme(values) / theme_toml_text(values) / default_theme()
"""

import copy
import tomllib

from lib import basemaps

_THEME_CONFIG_PATH = "config/theme.toml"

# 組み込み既定（config/theme.toml と同値）。ファイル未設定・キー欠損時のフォールバック。
_DEFAULTS: dict = {
    "facility_colors": {
        "認可保育所": "#2A78D6",   # 青
        "認定こども園": "#EB6834",  # 橙
        "幼稚園": "#4A3AA7",       # 紫
    },
    "facility_fallback": "#6B7280",   # 灰
    "circle_color": "#7C3AED",
    "circle_fill_opacity": 0.08,
    "band_color": "#7C3AED",
    "store_marker_color": "#111827",
    # 地図の背景（ベースマップ）。id は lib/basemaps.BASEMAPS を参照。
    "basemap": basemaps.DEFAULT_BASEMAP_ID,
    # 対話地図（画面表示）のサイズ（px）。
    "map_width": 700,
    "map_height": 560,
    # 対話地図の情報粒度（詳細度）を固定するズームレベル。
    # 0 = 固定しない（ズームに追従）。1–14 = そのズーム相当の粒度で固定。
    "map_detail_zoom": 0,
    # 推進園マーカー（番号付きの円）・店舗マーカー（カート）の相対サイズ（％）。
    # 100 = 既定サイズ。対話地図・ダウンロードPNGの両方に反映する。
    "facility_marker_size": 100,
    "store_marker_size": 100,
}

# 情報粒度固定ズームの許容範囲。0 は「固定しない」の意。
_DETAIL_ZOOM_MIN = 0
_DETAIL_ZOOM_MAX = 14

# 対話地図サイズ（px）の許容範囲。設定ページの入力・TOML 値の両方をこの範囲にクランプする。
_MAP_SIZE_MIN = 200
_MAP_SIZE_MAX = 2000

# マーカー相対サイズ（％）の許容範囲。設定ページの入力・TOML 値の両方をこの範囲にクランプする。
_MARKER_SIZE_MIN = 50
_MARKER_SIZE_MAX = 200

# スカラー（色/小数）のキー順。TOML 手組みと設定ページの両方で使う。
_SCALAR_KEYS = (
    "facility_fallback",
    "circle_color",
    "circle_fill_opacity",
    "band_color",
    "store_marker_color",
)

# defaults <- file <- overrides のマージ結果。get_theme() でキャッシュし save/apply で無効化。
_cache: dict | None = None
# プロセス内オーバーライド（読取専用FS でのプレビュー即時反映用）。
_overrides: dict = {}


def default_theme() -> dict:
    """組み込み既定テーマの複製を返す。"""
    return copy.deepcopy(_DEFAULTS)


def _load_from_file() -> dict:
    """config/theme.toml の [theme]（+ facility_colors）と [map] を読む。未存在時は空。"""
    try:
        with open(_THEME_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return {}
    loaded = dict(data.get("theme", {}) or {})
    map_section = data.get("map", {}) or {}
    for key in (
        "basemap",
        "map_width",
        "map_height",
        "map_detail_zoom",
        "facility_marker_size",
        "store_marker_size",
    ):
        if key in map_section:
            loaded[key] = map_section[key]
    return loaded


def _merge(base: dict, extra: dict) -> None:
    """extra の有効な値を base へ上書きマージ（facility_colors はキー単位で合成）。"""
    for key, value in extra.items():
        if key == "facility_colors" and isinstance(value, dict):
            fc = base.setdefault("facility_colors", {})
            for cat, col in value.items():
                if isinstance(col, str) and col:
                    fc[cat] = col
        elif key == "circle_fill_opacity":
            if isinstance(value, (int, float)):
                base[key] = float(value)
        elif key == "basemap":
            if isinstance(value, str) and basemaps.is_valid(value):
                base[key] = value
        elif key in ("map_width", "map_height"):
            if isinstance(value, (int, float)) and value > 0:
                base[key] = max(_MAP_SIZE_MIN, min(_MAP_SIZE_MAX, int(value)))
        elif key == "map_detail_zoom":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                base[key] = max(_DETAIL_ZOOM_MIN, min(_DETAIL_ZOOM_MAX, int(value)))
        elif key in ("facility_marker_size", "store_marker_size"):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                base[key] = max(_MARKER_SIZE_MIN, min(_MARKER_SIZE_MAX, int(value)))
        elif key in _SCALAR_KEYS:
            if isinstance(value, str) and value:
                base[key] = value


def get_theme() -> dict:
    """既定 <- config/theme.toml <- プロセス内オーバーライド をマージしたテーマを返す。"""
    global _cache
    if _cache is None:
        theme = default_theme()
        _merge(theme, _load_from_file())
        _merge(theme, _overrides)
        _cache = theme
    return _cache


def reload_theme() -> None:
    """キャッシュを破棄し、次回 get_theme() でファイルから再読込させる。"""
    global _cache
    _cache = None


def apply_overrides(values: dict) -> None:
    """プロセス内オーバーライドを差し込む（読取専用FS でのプレビュー即時反映用）。"""
    _merge(_overrides, values)
    reload_theme()


# --- render-time accessors --------------------------------------------------

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """``"#RRGGBB"`` を ``(R, G, B)`` タプルへ変換する。"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def facility_colors() -> dict[str, str]:
    """推進園区分 -> 色 の辞書（定義順は凡例の表示順）。"""
    return get_theme()["facility_colors"]


def facility_color(category: str) -> str:
    """推進園区分に対応する16進色を返す（未知値はフォールバック色）。"""
    return facility_colors().get(category, get_theme()["facility_fallback"])


def facility_color_rgb(category: str) -> tuple[int, int, int]:
    """推進園区分に対応する ``(R, G, B)`` タプルを返す（未知値はフォールバック色）。"""
    return hex_to_rgb(facility_color(category))


def circle_color() -> str:
    """半径円の線色（16進）。"""
    return get_theme()["circle_color"]


def circle_color_rgb() -> tuple[int, int, int]:
    """半径円の線色（RGB）。"""
    return hex_to_rgb(circle_color())


def circle_fill_opacity() -> float:
    """半径円の塗り透明度（0.0–1.0）。"""
    return float(get_theme()["circle_fill_opacity"])


def band_color() -> str:
    """見出し帯・施設リストヘッダーの背景色（16進）。"""
    return get_theme()["band_color"]


def band_color_rgb() -> tuple[int, int, int]:
    """見出し帯の背景色（RGB）。"""
    return hex_to_rgb(band_color())


def store_marker_color() -> str:
    """中心の店舗マーカー色（16進）。"""
    return get_theme()["store_marker_color"]


def store_marker_color_rgb() -> tuple[int, int, int]:
    """中心の店舗マーカー色（RGB）。"""
    return hex_to_rgb(store_marker_color())


def basemap_id() -> str:
    """選択中の地図ベースマップ id（未知値は既定へフォールバック）。"""
    bid = get_theme().get("basemap", basemaps.DEFAULT_BASEMAP_ID)
    return bid if basemaps.is_valid(bid) else basemaps.DEFAULT_BASEMAP_ID


def map_width() -> int:
    """対話地図（画面表示）の幅（px）。"""
    return int(get_theme()["map_width"])


def map_height() -> int:
    """対話地図（画面表示）の高さ（px）。半径円が収まるズーム算出の基準にも使う。"""
    return int(get_theme()["map_height"])


def map_detail_zoom() -> int:
    """対話地図の情報粒度を固定するズーム（0=固定しない、1–14=その粒度で固定）。"""
    return int(get_theme()["map_detail_zoom"])


def facility_marker_size() -> int:
    """推進園マーカー（番号付きの円）の相対サイズ（％、100=既定）。"""
    return int(get_theme()["facility_marker_size"])


def store_marker_size() -> int:
    """店舗マーカー（カート）の相対サイズ（％、100=既定）。"""
    return int(get_theme()["store_marker_size"])


# --- persistence ------------------------------------------------------------

def theme_toml_text(values: dict) -> str:
    """*values*（get_theme() 形式）を config/theme.toml と同じ書式の TOML 文字列にする。"""
    theme = default_theme()
    _merge(theme, values)
    lines = [
        "# 画面・PNG の配色テーマ設定（SPEC §6.1.2 / §8.3）。",
        "# 「テーマ設定」ページで生成。値は 16進カラー（circle_fill_opacity のみ 0.0–1.0）。",
        "",
        "[theme]",
        f'facility_fallback   = "{theme["facility_fallback"]}"',
        f'circle_color        = "{theme["circle_color"]}"',
        f"circle_fill_opacity = {theme['circle_fill_opacity']}",
        f'band_color          = "{theme["band_color"]}"',
        f'store_marker_color  = "{theme["store_marker_color"]}"',
        "",
        "[theme.facility_colors]",
    ]
    for cat, col in theme["facility_colors"].items():
        lines.append(f'"{cat}" = "{col}"')
    lines += [
        "",
        "# 地図の背景（ベースマップ）。id は lib/basemaps.py の BASEMAPS を参照。",
        "[map]",
        f'basemap = "{theme["basemap"]}"',
        "# 対話地図（画面表示）のサイズ（px）。",
        f'map_width  = {int(theme["map_width"])}',
        f'map_height = {int(theme["map_height"])}',
        "# 対話地図の情報粒度を固定するズーム（0=固定しない、1–14=その粒度で固定）。",
        f'map_detail_zoom = {int(theme["map_detail_zoom"])}',
        "# 推進園マーカー・店舗マーカーの相対サイズ（％、100=既定）。対話地図・PNG両方に反映。",
        f'facility_marker_size = {int(theme["facility_marker_size"])}',
        f'store_marker_size    = {int(theme["store_marker_size"])}',
    ]
    return "\n".join(lines) + "\n"


def save_theme(values: dict) -> str:
    """*values* を config/theme.toml へ書き込み、テーマを再読込する。

    書き込みに失敗（読取専用FS 等）した場合は例外を送出する（呼び出し側で処理）。
    成功時は書き込んだパスを返す。
    """
    text = theme_toml_text(values)
    with open(_THEME_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    reload_theme()
    return _THEME_CONFIG_PATH
