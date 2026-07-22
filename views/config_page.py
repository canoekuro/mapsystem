"""
テーマ設定ページ。

施設の色（単一色）・半径円・見出し帯の配色と、地図の背景（ベースマップ）・マーカーサイズを
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
# 施設の色は区分色分けを廃止し単一色（facility_color）で扱う（issue 202607221414）。
_SCALAR_PICKERS = [
    ("cfg_facility_color", "施設の色", "facility_color"),
    ("cfg_circle_color", "半径円の線色", "circle_color"),
    ("cfg_band_color", "見出し帯・施設リストヘッダー", "band_color"),
]
_OPACITY_KEY = "cfg_circle_fill_opacity"


_BASEMAP_KEY = "cfg_basemap"
_MAP_WIDTH_KEY = "cfg_map_width"
_MAP_HEIGHT_KEY = "cfg_map_height"
_MAP_DETAIL_ZOOM_KEY = "cfg_map_detail_zoom"
_STORE_MARKER_SIZE_KEY = "cfg_store_marker_size"
_CAPTION_KEY = "cfg_store_caption_format"

# 推進園マーカーサイズ（半径バケット別）の session_state キーとラベル。
# theme["facility_marker_sizes"] の要素順（[≤1,≤2,≤3,≤4,≤5,>5]km）に対応する。
_FACILITY_MARKER_SIZE_KEYS = [f"cfg_facility_marker_size_{i}" for i in range(6)]
_FACILITY_MARKER_SIZE_LABELS = [
    "半径1km以下", "2km以下", "3km以下", "4km以下", "5km以下", "5km超",
]


def _init_state() -> None:
    """未初期化のウィジェット状態を現在のテーマ値で埋める。"""
    current = theme.get_theme()
    for key, _label, tkey in _SCALAR_PICKERS:
        st.session_state.setdefault(key, current[tkey])
    st.session_state.setdefault(_OPACITY_KEY, float(current["circle_fill_opacity"]))
    st.session_state.setdefault(_BASEMAP_KEY, theme.basemap_id())
    st.session_state.setdefault(_MAP_WIDTH_KEY, int(current["map_width"]))
    st.session_state.setdefault(_MAP_HEIGHT_KEY, int(current["map_height"]))
    st.session_state.setdefault(_MAP_DETAIL_ZOOM_KEY, int(current["map_detail_zoom"]))
    for key, size in zip(_FACILITY_MARKER_SIZE_KEYS, current["facility_marker_sizes"]):
        st.session_state.setdefault(key, int(size))
    st.session_state.setdefault(_STORE_MARKER_SIZE_KEY, int(current["store_marker_size"]))
    st.session_state.setdefault(_CAPTION_KEY, current["store_caption_format"])


def _reset_to_default() -> None:
    """ウィジェット状態を組み込み既定へ戻す（保存はしない）。"""
    d = theme.default_theme()
    for key, _label, tkey in _SCALAR_PICKERS:
        st.session_state[key] = d[tkey]
    st.session_state[_OPACITY_KEY] = float(d["circle_fill_opacity"])
    # ベースマップと、それに連動する提供元/スタイルのウィジェット状態も既定へ。
    st.session_state[_BASEMAP_KEY] = d["basemap"]
    default_provider = basemaps.get_basemap(d["basemap"])["provider"]
    st.session_state["cfg_map_provider"] = default_provider
    st.session_state[f"cfg_map_style_{default_provider}"] = basemaps.get_basemap(d["basemap"])["label"]
    st.session_state[_MAP_WIDTH_KEY] = int(d["map_width"])
    st.session_state[_MAP_HEIGHT_KEY] = int(d["map_height"])
    st.session_state[_MAP_DETAIL_ZOOM_KEY] = int(d["map_detail_zoom"])
    for key, size in zip(_FACILITY_MARKER_SIZE_KEYS, d["facility_marker_sizes"]):
        st.session_state[key] = int(size)
    st.session_state[_STORE_MARKER_SIZE_KEY] = int(d["store_marker_size"])
    st.session_state[_CAPTION_KEY] = d["store_caption_format"]


def _collect_values() -> dict:
    """現在のウィジェット状態を theme 形式の dict にまとめる。"""
    values = {tkey: st.session_state[key] for key, _label, tkey in _SCALAR_PICKERS}
    values["circle_fill_opacity"] = float(st.session_state[_OPACITY_KEY])
    values["basemap"] = st.session_state[_BASEMAP_KEY]
    values["map_width"] = int(st.session_state[_MAP_WIDTH_KEY])
    values["map_height"] = int(st.session_state[_MAP_HEIGHT_KEY])
    values["map_detail_zoom"] = int(st.session_state[_MAP_DETAIL_ZOOM_KEY])
    values["facility_marker_sizes"] = [
        int(st.session_state[key]) for key in _FACILITY_MARKER_SIZE_KEYS
    ]
    values["store_marker_size"] = int(st.session_state[_STORE_MARKER_SIZE_KEY])
    values["store_caption_format"] = st.session_state[_CAPTION_KEY]
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
    """選択中の配色でプレビュー（見出し帯・施設リスト・半径円）を組む。

    施設は単一色（区分色分けは廃止, issue 202607221414）なので凡例は表示しない。
    """
    band = values["band_color"]
    circle = values["circle_color"]
    opacity = values["circle_fill_opacity"]
    facility = values["facility_color"]
    # プレビューのバッジは半径非依存のため固定サイズ（100%相当）で描画する。
    badge_px = 24
    badge_font_px = 12

    band_bar = (
        f'<div style="background:{band};color:#fff;height:40px;display:flex;'
        "align-items:center;justify-content:center;font-weight:bold;"
        'border-radius:6px;margin-bottom:10px;">見出し帯・施設リスト</div>'
    )
    # 施設は単一色。番号バッジのサンプルを数個並べる（全て同色）。
    badges = "".join(
        f'<div style="display:flex;align-items:center;margin:4px 0;">'
        f'<span style="width:{badge_px}px;height:{badge_px}px;border-radius:50%;background:{facility};'
        "color:#fff;display:flex;align-items:center;justify-content:center;"
        f'font-size:{badge_font_px}px;font-weight:bold;flex-shrink:0;">{i}</span>'
        f'<span style="margin-left:8px;font-size:13px;color:#111827;">推進園サンプル {i}</span>'
        "</div>"
        for i in range(1, 4)
    )
    # 円の塗りは rgba で透明度を反映する
    r, g, b = theme.hex_to_rgb(circle)
    circle_swatch = (
        f'<div style="width:96px;height:96px;border-radius:50%;'
        f"border:3px dashed {circle};"
        f'background:rgba({r},{g},{b},{opacity});"></div>'
    )
    return (
        '<div style="border:1px solid #E5E7EB;border-radius:8px;padding:16px;">'
        f"{band_bar}"
        '<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start;">'
        f'<div><div style="font-size:12px;color:#6B7280;margin-bottom:4px;">施設リスト</div>{badges}</div>'
        f'<div><div style="font-size:12px;color:#6B7280;margin-bottom:4px;">半径円</div>{circle_swatch}</div>'
        "</div></div>"
    )


def render() -> None:
    """Render the theme-config page."""
    st.header("テーマ設定")
    st.info(
        "施設の色（単一色）・半径円・見出し帯の色と、地図の背景・マーカーサイズを調整できます。"
        "「保存」で config/theme.toml に書き込み、地図・ダウンロードPNG・pptx へ反映されます。"
    )

    _init_state()

    st.subheader("施設の色")
    st.caption("推進園マーカー（番号付きの円）・施設リストバッジの色。区分による色分けは廃止しています。")
    st.color_picker("施設の色", key="cfg_facility_color")

    st.subheader("半径円")
    c1, c2 = st.columns(2)
    with c1:
        st.color_picker("半径円の線色", key="cfg_circle_color")
    with c2:
        st.slider(
            "塗り透明度", min_value=0.0, max_value=0.5, step=0.01, key=_OPACITY_KEY
        )

    st.subheader("見出し帯")
    st.color_picker("見出し帯・施設リストヘッダー", key="cfg_band_color")

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
        "詳細度ズーム", min_value=0, max_value=14, step=1, key=_MAP_DETAIL_ZOOM_KEY
    )

    st.subheader("推進園マーカーサイズ（地図半径別）")
    st.caption(
        "推進園マーカー（番号付きの円）の大きさ（％、100＝既定）を地図半径ごとに指定します。"
        "対話地図・ダウンロードPNGの両方に反映されます。"
    )
    fm_cols = st.columns(len(_FACILITY_MARKER_SIZE_KEYS))
    for col, key, label in zip(fm_cols, _FACILITY_MARKER_SIZE_KEYS, _FACILITY_MARKER_SIZE_LABELS):
        with col:
            st.number_input(
                f"{label}(%)", min_value=50, max_value=200, step=10, key=key,
            )

    st.subheader("店舗マーカーサイズ")
    st.caption("店舗マーカー（画像アイコン）の大きさ（％、100＝既定）。両方に反映されます。")
    st.number_input(
        "店舗マーカー(%)", min_value=50, max_value=200, step=10,
        key=_STORE_MARKER_SIZE_KEY,
    )

    st.subheader("資料キャプション（pptx）")
    st.caption(
        "商談用資料・店舗POP のテキスト枠に入る定型文。"
        "{store} が選択中の小売店名称に置換されます。"
    )
    st.text_input("キャプション定型文", key=_CAPTION_KEY)
    try:
        st.caption(f"例: {str(st.session_state[_CAPTION_KEY]).format(store='サンプル店')}")
    except (KeyError, IndexError, ValueError):
        st.warning("定型文の書式が不正です（利用できる差込みは {store} のみです）。")

    values = _collect_values()

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
