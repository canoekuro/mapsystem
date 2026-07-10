"""
テーマ設定ページ。

凡例（推進園区分）・半径円・見出し帯・店舗マーカーの配色と、地図の背景（ベースマップ）を
画面から調整する。値は lib.colors のテーマ（config/theme.toml）を source of truth とし、
「保存」で config/theme.toml を書き換える。Databricks Apps はファイルシステムが揮発性のため、
恒久化するには「設定TOMLをダウンロード」で得た内容をリポジトリにコミットすること。

Public API
----------
render() -- render the theme-config page.
"""

import logging

import streamlit as st

from lib import basemaps
from lib import colors as theme

logger = logging.getLogger(__name__)

# (session_state キー, ラベル, テーマキー)
_SCALAR_PICKERS = [
    ("cfg_circle_color", "半径円の線色", "circle_color"),
    ("cfg_band_color", "見出し帯・施設リストヘッダー", "band_color"),
    ("cfg_store_marker_color", "店舗マーカー色", "store_marker_color"),
    ("cfg_facility_fallback", "区分フォールバック（想定外/未設定）", "facility_fallback"),
]
_OPACITY_KEY = "cfg_circle_fill_opacity"


def _facility_key(category: str) -> str:
    return f"cfg_facility_{category}"


_BASEMAP_KEY = "cfg_basemap"
_MAP_WIDTH_KEY = "cfg_map_width"
_MAP_HEIGHT_KEY = "cfg_map_height"
_MAP_DETAIL_ZOOM_KEY = "cfg_map_detail_zoom"


def _init_state() -> None:
    """未初期化のウィジェット状態を現在のテーマ値で埋める。"""
    current = theme.get_theme()
    for key, _label, tkey in _SCALAR_PICKERS:
        st.session_state.setdefault(key, current[tkey])
    st.session_state.setdefault(_OPACITY_KEY, float(current["circle_fill_opacity"]))
    for category, color in current["facility_colors"].items():
        st.session_state.setdefault(_facility_key(category), color)
    st.session_state.setdefault(_BASEMAP_KEY, theme.basemap_id())
    st.session_state.setdefault(_MAP_WIDTH_KEY, int(current["map_width"]))
    st.session_state.setdefault(_MAP_HEIGHT_KEY, int(current["map_height"]))
    st.session_state.setdefault(_MAP_DETAIL_ZOOM_KEY, int(current["map_detail_zoom"]))


def _reset_to_default() -> None:
    """ウィジェット状態を組み込み既定へ戻す（保存はしない）。"""
    d = theme.default_theme()
    for key, _label, tkey in _SCALAR_PICKERS:
        st.session_state[key] = d[tkey]
    st.session_state[_OPACITY_KEY] = float(d["circle_fill_opacity"])
    for category, color in d["facility_colors"].items():
        st.session_state[_facility_key(category)] = color
    # ベースマップと、それに連動する提供元/スタイルのウィジェット状態も既定へ。
    st.session_state[_BASEMAP_KEY] = d["basemap"]
    default_provider = basemaps.get_basemap(d["basemap"])["provider"]
    st.session_state["cfg_map_provider"] = default_provider
    st.session_state[f"cfg_map_style_{default_provider}"] = basemaps.get_basemap(d["basemap"])["label"]
    st.session_state[_MAP_WIDTH_KEY] = int(d["map_width"])
    st.session_state[_MAP_HEIGHT_KEY] = int(d["map_height"])
    st.session_state[_MAP_DETAIL_ZOOM_KEY] = int(d["map_detail_zoom"])


def _collect_values(categories: list[str]) -> dict:
    """現在のウィジェット状態を theme 形式の dict にまとめる。"""
    values = {tkey: st.session_state[key] for key, _label, tkey in _SCALAR_PICKERS}
    values["circle_fill_opacity"] = float(st.session_state[_OPACITY_KEY])
    values["facility_colors"] = {
        cat: st.session_state[_facility_key(cat)] for cat in categories
    }
    values["basemap"] = st.session_state[_BASEMAP_KEY]
    values["map_width"] = int(st.session_state[_MAP_WIDTH_KEY])
    values["map_height"] = int(st.session_state[_MAP_HEIGHT_KEY])
    values["map_detail_zoom"] = int(st.session_state[_MAP_DETAIL_ZOOM_KEY])
    return values


def _basemap_selector() -> None:
    """提供元→スタイルの2段セレクトで地図の背景を選ぶ。結果を session_state に反映。"""
    current_id = st.session_state[_BASEMAP_KEY]
    current_provider = basemaps.get_basemap(current_id)["provider"]

    provider_opts = basemaps.providers()
    st.session_state.setdefault("cfg_map_provider", current_provider)
    p1, p2 = st.columns(2)
    with p1:
        provider = st.selectbox("提供元", provider_opts, key="cfg_map_provider")

    opts = basemaps.basemaps_for_provider(provider)
    labels = [cfg["label"] for _bid, cfg in opts]
    ids = [bid for bid, _cfg in opts]
    style_key = f"cfg_map_style_{provider}"
    # 提供元に現在の basemap が属していればそのラベル、なければ先頭を既定に。
    default_label = basemaps.get_basemap(current_id)["label"] if current_id in ids else labels[0]
    st.session_state.setdefault(style_key, default_label)
    with p2:
        label = st.selectbox("スタイル", labels, key=style_key)

    st.session_state[_BASEMAP_KEY] = ids[labels.index(label)]


def _preview_html(values: dict) -> str:
    """選択中の配色でプレビュー（見出し帯・凡例・施設リスト・半径円）を組む。"""
    band = values["band_color"]
    circle = values["circle_color"]
    opacity = values["circle_fill_opacity"]
    store = values["store_marker_color"]
    fac = values["facility_colors"]

    band_bar = (
        f'<div style="background:{band};color:#fff;height:40px;display:flex;'
        "align-items:center;justify-content:center;font-weight:bold;"
        'border-radius:6px;margin-bottom:10px;">見出し帯・施設リスト</div>'
    )
    legend_rows = "".join(
        f'<div style="display:flex;align-items:center;margin:2px 0;">'
        f'<span style="width:14px;height:14px;border-radius:50%;background:{col};'
        'display:inline-block;margin-right:8px;"></span>'
        f'<span style="font-size:13px;color:#111827;">{cat}</span></div>'
        for cat, col in fac.items()
    )
    legend = (
        '<div style="display:inline-block;background:#fff;border:1px solid #E5E7EB;'
        'border-radius:6px;padding:8px 12px;box-shadow:0 1px 4px rgba(0,0,0,0.15);">'
        '<div style="font-size:13px;font-weight:bold;margin-bottom:4px;">推進園区分</div>'
        f"{legend_rows}</div>"
    )
    badges = "".join(
        f'<div style="display:flex;align-items:center;margin:4px 0;">'
        f'<span style="width:24px;height:24px;border-radius:50%;background:{col};'
        "color:#fff;display:flex;align-items:center;justify-content:center;"
        f'font-size:12px;font-weight:bold;">{i}</span>'
        f'<span style="margin-left:8px;font-size:13px;color:#111827;">{cat} サンプル</span>'
        "</div>"
        for i, (cat, col) in enumerate(fac.items(), start=1)
    )
    # 円の塗りは rgba で透明度を反映する
    r, g, b = theme.hex_to_rgb(circle)
    circle_swatch = (
        f'<div style="width:96px;height:96px;border-radius:50%;'
        f"border:3px dashed {circle};"
        f'background:rgba({r},{g},{b},{opacity});display:flex;align-items:center;'
        "justify-content:center;\">"
        f'<span style="width:20px;height:20px;border-radius:50%;background:{store};'
        'border:3px solid #fff;box-shadow:0 0 0 1px #999;"></span></div>'
    )
    return (
        '<div style="border:1px solid #E5E7EB;border-radius:8px;padding:16px;">'
        f"{band_bar}"
        '<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start;">'
        f'<div>{legend}</div>'
        f'<div><div style="font-size:12px;color:#6B7280;margin-bottom:4px;">施設リスト</div>{badges}</div>'
        f'<div><div style="font-size:12px;color:#6B7280;margin-bottom:4px;">半径円＋店舗</div>{circle_swatch}</div>'
        "</div></div>"
    )


def render() -> None:
    """Render the theme-config page."""
    st.header("テーマ設定")
    st.info(
        "凡例（推進園区分）・半径円・見出し帯・店舗マーカーの色と、地図の背景を調整できます。"
        "「保存」で config/theme.toml に書き込み、地図とダウンロードPNGの両方へ反映されます。"
    )

    _init_state()
    categories = list(theme.get_theme()["facility_colors"].keys())

    st.subheader("推進園区分の色（凡例・マーカー）")
    fac_cols = st.columns(max(len(categories), 1))
    for col, category in zip(fac_cols, categories):
        with col:
            st.color_picker(category, key=_facility_key(category))
    st.color_picker(
        "区分フォールバック（想定外/未設定）", key="cfg_facility_fallback"
    )

    st.subheader("半径円")
    c1, c2 = st.columns(2)
    with c1:
        st.color_picker("半径円の線色", key="cfg_circle_color")
    with c2:
        st.slider(
            "塗り透明度", min_value=0.0, max_value=0.5, step=0.01, key=_OPACITY_KEY
        )

    st.subheader("見出し帯・店舗マーカー")
    b1, b2 = st.columns(2)
    with b1:
        st.color_picker("見出し帯・施設リストヘッダー", key="cfg_band_color")
    with b2:
        st.color_picker("店舗マーカー色", key="cfg_store_marker_color")

    st.subheader("地図の背景")
    _basemap_selector()

    st.subheader("地図サイズ（画面表示）")
    st.caption("マップページの対話地図の大きさ（px）。ダウンロードPNGのサイズは変わりません。")
    s1, s2 = st.columns(2)
    with s1:
        st.number_input(
            "幅(px)", min_value=500, max_value=1200, step=20, key=_MAP_WIDTH_KEY
        )
    with s2:
        st.number_input(
            "高さ(px)", min_value=400, max_value=1000, step=20, key=_MAP_HEIGHT_KEY
        )

    st.subheader("情報の粒度（詳細度）")
    st.caption(
        "0＝固定しない（ズームに追従）。1以上＝そのズーム相当の詳細度で固定し、"
        "地図をズームしても表示情報の粒度が変わりません（拡大するとぼやけます）。"
        "対話地図のみ。ダウンロードPNGには影響しません。"
    )
    st.number_input(
        "詳細度ズーム", min_value=0, max_value=19, step=1, key=_MAP_DETAIL_ZOOM_KEY
    )

    values = _collect_values(categories)

    bm = basemaps.get_basemap(values["basemap"])
    st.caption(f"選択中の背景: {bm['provider']} / {bm['label']}　｜　帰属表示: {bm['attribution']}")

    st.subheader("プレビュー")
    st.markdown(_preview_html(values), unsafe_allow_html=True)

    st.divider()
    a1, a2, a3 = st.columns([1, 1, 1])
    with a1:
        if st.button("保存", type="primary", use_container_width=True):
            try:
                path = theme.save_theme(values)
                st.success(f"保存しました → {path}")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                # 読取専用FS（Databricks Apps 等）: プロセス内へ適用しつつ DL を促す。
                logger.warning("theme.toml の保存に失敗: %s", e)
                theme.apply_overrides(values)
                st.warning(
                    "ファイルへの保存に失敗しました（読取専用の可能性）。"
                    "今回の表示には反映しました。恒久化するには下の"
                    "「設定TOMLをダウンロード」からリポジトリにコミットしてください。"
                )
    with a2:
        st.download_button(
            "設定TOMLをダウンロード",
            data=theme.theme_toml_text(values),
            file_name="theme.toml",
            mime="text/plain",
            use_container_width=True,
        )
    with a3:
        if st.button("既定に戻す", use_container_width=True):
            _reset_to_default()
            st.rerun()
