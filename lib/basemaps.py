"""
地図ベースマップ（背景タイル）のカタログ（SPEC §6.1.2）。

対話地図(folium)・PNG合成(static_map) の双方で使うラスターXYZタイルの定義。
選択中のベースマップ id は設定（config/theme.toml `[map]`、lib.colors）で保持し、
ここは純粋なカタログ（id -> 定義）と参照ヘルパーのみを持つ（永続化の責務は持たない）。

各定義のキー:
- ``label``       : 表示名（設定ページのスタイル選択）
- ``provider``    : 提供元グループ名（設定ページの提供元選択）
- ``url``         : XYZ タイル URL テンプレート（``{z}/{x}/{y}``、単一ホスト＝``{s}`` 不使用）
- ``attribution`` : 帰属表示（地図・PNG に表示。各提供元とも必須）
- ``max_zoom``    : そのタイルが提供する最大ズーム
"""

_OSM_ATTR = "© OpenStreetMap contributors"
_GSI_ATTR = "出典: 地理院タイルに店舗・推進園情報を追記して掲載"
_CARTO_ATTR = "© OpenStreetMap contributors © CARTO"

PROVIDER_OSM = "OpenStreetMap"
PROVIDER_GSI = "国土地理院"
PROVIDER_CARTO = "CARTO"

# id -> 定義。dict の順序が提供元／スタイルの表示順を兼ねる。
BASEMAPS: dict[str, dict] = {
    # --- OpenStreetMap ---
    "osm_standard": {
        "label": "標準",
        "provider": PROVIDER_OSM,
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": _OSM_ATTR,
        "max_zoom": 19,
    },
    "osm_hot": {
        "label": "Humanitarian",
        "provider": PROVIDER_OSM,
        "url": "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        "attribution": f"{_OSM_ATTR}, Tiles: Humanitarian OSM Team",
        "max_zoom": 19,
    },
    "osmfj_japan": {
        "label": "日本語スタイル",
        "provider": PROVIDER_OSM,
        "url": "https://tile.openstreetmap.jp/{z}/{x}/{y}.png",
        "attribution": f"{_OSM_ATTR}, Tiles: OSMFJ",
        "max_zoom": 18,
    },
    # --- 国土地理院（GSI） ---
    "gsi_std": {
        "label": "標準地図",
        "provider": PROVIDER_GSI,
        "url": "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png",
        "attribution": _GSI_ATTR,
        "max_zoom": 18,
    },
    "gsi_pale": {
        "label": "淡色地図",
        "provider": PROVIDER_GSI,
        "url": "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
        "attribution": _GSI_ATTR,
        "max_zoom": 18,
    },
    "gsi_photo": {
        "label": "航空写真",
        "provider": PROVIDER_GSI,
        "url": "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg",
        "attribution": _GSI_ATTR,
        "max_zoom": 18,
    },
    "gsi_blank": {
        "label": "白地図",
        "provider": PROVIDER_GSI,
        "url": "https://cyberjapandata.gsi.go.jp/xyz/blank/{z}/{x}/{y}.png",
        "attribution": _GSI_ATTR,
        "max_zoom": 14,
    },
    # --- CARTO（OSM ベース） ---
    "carto_positron": {
        "label": "Positron（淡色）",
        "provider": PROVIDER_CARTO,
        "url": "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "attribution": _CARTO_ATTR,
        "max_zoom": 20,
    },
    "carto_voyager": {
        "label": "Voyager",
        "provider": PROVIDER_CARTO,
        "url": "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "attribution": _CARTO_ATTR,
        "max_zoom": 20,
    },
    "carto_dark": {
        "label": "Dark Matter（ダーク）",
        "provider": PROVIDER_CARTO,
        "url": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "attribution": _CARTO_ATTR,
        "max_zoom": 20,
    },
}

DEFAULT_BASEMAP_ID = "gsi_pale"


def get_basemap(basemap_id: str) -> dict:
    """id に対応する定義を返す（未知 id は既定へフォールバック）。"""
    return BASEMAPS.get(basemap_id, BASEMAPS[DEFAULT_BASEMAP_ID])


def is_valid(basemap_id: str) -> bool:
    """既知の basemap id か。"""
    return basemap_id in BASEMAPS


def basemap_ids() -> list[str]:
    """全 basemap id（定義順）。"""
    return list(BASEMAPS)


def providers() -> list[str]:
    """提供元グループ名（重複排除・出現順）。"""
    seen: list[str] = []
    for cfg in BASEMAPS.values():
        if cfg["provider"] not in seen:
            seen.append(cfg["provider"])
    return seen


def basemaps_for_provider(provider: str) -> list[tuple[str, dict]]:
    """指定提供元の (id, 定義) を定義順で返す。"""
    return [(bid, cfg) for bid, cfg in BASEMAPS.items() if cfg["provider"] == provider]
