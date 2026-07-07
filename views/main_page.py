"""
単一ページ画面: 企業/小売店/半径の選択、企業一括ダウンロード、地図＋施設リスト、出典フッタ。

Public API
----------
render(df) -- render the whole single-page app.
"""

import logging

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from lib.colors import band_color, facility_color
from lib.data import (
    load_filtered,
    stores_for_company,
    filter_facilities,
    filter_company,
    prefectures_for_company,
    stores_for_company_prefectures,
    store_count_for_company_prefectures,
)
from lib.map_builder import build_map
from lib.zip_builder import build_png_zip

logger = logging.getLogger(__name__)


# df is excluded from the cache key (hash_funcs returns None): it is uniquely
# determined by the already-fetched (company, radius), which are part of the key.
@st.cache_data(show_spinner="画像を生成中...", hash_funcs={pd.DataFrame: lambda _df: None})
def _company_image_zip(df: pd.DataFrame, company: str, prefectures: tuple, radius: float) -> bytes:
    names = stores_for_company_prefectures(df, company, list(prefectures))
    return build_png_zip(df, names, radius)


def _header_html(store: str, radius: float) -> str:
    return (
        f'<div style="'
        f"background-color:{band_color()};"
        f"color:#FFFFFF;height:64px;display:flex;align-items:center;"
        f"padding-left:24px;font-size:22px;font-weight:bold;"
        f"border-radius:8px;margin-bottom:12px;"
        f'">'
        f"{store} 周辺マップ概要 ｜ 半径{radius}km圏内"
        f"</div>"
    )


def _facility_list_html(fac) -> str:
    parts: list[str] = []
    parts.append(
        '<div style="'
        f"background-color:{band_color()};"
        "color:#FFFFFF;height:40px;display:flex;align-items:center;"
        "justify-content:center;font-size:16px;font-weight:bold;"
        "border-radius:4px 4px 0 0;"
        '">'
        "施設リスト"
        "</div>"
    )
    for _, row in fac.iterrows():
        color = facility_color(row["推進園区分"])
        number = int(row["連番"])
        name = row["推進園名称"]
        distance = row["距離km"]
        badge = (
            '<div style="'
            f"background-color:{color};"
            "color:#FFFFFF;width:24px;height:24px;border-radius:50%;"
            "display:flex;align-items:center;justify-content:center;"
            "font-size:11px;font-weight:bold;flex-shrink:0;"
            '">'
            f"{number}"
            "</div>"
        )
        info = (
            '<div style="margin-left:8px;">'
            f'<div style="font-size:14px;font-weight:bold;color:#111827;">{name}</div>'
            f'<div style="font-size:12px;color:#6B7280;">約{distance:.2f}km</div>'
            "</div>"
        )
        parts.append(
            '<div style="'
            "display:flex;align-items:center;background-color:#FFFFFF;"
            "border-bottom:1px solid #E5E7EB;padding:8px 8px;"
            '">'
            f"{badge}{info}"
            "</div>"
        )
    return "\n".join(parts)


def _data_source_caption() -> None:
    st.divider()
    st.caption(
        "データ出典: 位置参照情報（大字町丁目・街区レベル）令和6年（国土交通省）、"
        "電子国土基本図（地名情報）住居表示住所（国土地理院）、"
        "Geolonia 住所データ（株式会社Geolonia）"
        " [japanese-addresses](https://geolonia.github.io/japanese-addresses/)、"
        "アドレス・ベース・レジストリ（デジタル庁）"
        " [base_registry_address](https://www.digital.go.jp/policies/base_registry_address_tos/)、"
        "登記所備付地図データ（法務省）をもとに、株式会社情報試作室が加工した"
        " jageocoder 用住所データベース（住居表示レベル）を利用"
    )


def render(companies: list[str]) -> None:
    """Render the single-page app.

    *companies* is the list of distinct company names (loaded at startup).
    The filtered DataFrame is fetched on demand when データ取得 is pressed and
    kept in st.session_state.
    """
    # --- 取得行（常時表示）: 企業 + 取得半径 + データ取得ボタン ---
    g1, g2, g3 = st.columns([2, 1, 1])
    with g1:
        company = st.selectbox(
            "企業名称", companies, index=None, placeholder="企業を選択してください"
        )
    with g2:
        fetch_radius = st.number_input(
            "取得半径(km)", min_value=0.1, max_value=50.0,
            value=None, step=0.1, placeholder="半径を入力",
        )
    with g3:
        # ラベル高さ分のスペーサで selectbox/number_input と縦位置を揃える。
        st.write("")
        st.write("")
        fetch_disabled = company is None or fetch_radius is None
        fetch_clicked = st.button(
            "データ取得", disabled=fetch_disabled, use_container_width=True, type="primary"
        )

    # データ取得: 企業 + 取得半径で Databricks 側を絞り込んで取得し、session_state に保存。
    if fetch_clicked:
        st.session_state["loaded_df"] = load_filtered(company, fetch_radius)
        st.session_state["loaded_company"] = company
        st.session_state["loaded_fetch_radius"] = fetch_radius

    # 未取得なら案内のみ表示して終了。
    if "loaded_df" not in st.session_state:
        st.info("企業名称と取得半径を入力して「データ取得」を押してください")
        _data_source_caption()
        return

    df = st.session_state["loaded_df"]
    loaded_company = st.session_state["loaded_company"]
    loaded_fetch_radius = st.session_state["loaded_fetch_radius"]

    # --- 取得件数サマリ（取得後は常時表示）---
    # 0件のとき選択肢が空になるだけで取得失敗と区別できない問題を避けるため、
    # 取得した行数と選択肢になる店舗数を明示する（取得済みDFから都度算出）。
    n_rows = len(df)
    n_stores = df["店舗名称"].nunique() if n_rows else 0
    if n_rows == 0:
        st.warning(
            f"取得結果: 0件 — {loaded_company} / 半径{loaded_fetch_radius}km に"
            "該当するデータがありませんでした（取得処理は成功しています）"
        )
    else:
        st.success(f"取得結果: {n_rows:,}件（店舗数: {n_stores:,}）")

    # 現在の入力が取得済み条件と異なる場合は案内（旧データは表示し続ける）。
    changed = (company is not None and company != loaded_company) or (
        fetch_radius is not None and fetch_radius != loaded_fetch_radius
    )
    if changed:
        st.info(
            f"現在の入力（{company} / {fetch_radius}km）は取得済みデータ"
            f"（{loaded_company} / {loaded_fetch_radius}km）と異なります。"
            "「データ取得」を押すと再取得します。"
        )

    # --- 表示行（取得後のみ）: 小売店 + 表示半径 ---
    d1, d2 = st.columns([2, 1])
    with d1:
        store = st.selectbox(
            "小売店名称", stores_for_company(df, loaded_company),
            index=None, placeholder="店舗を選択してください",
        )
    with d2:
        # 表示半径は取得半径以下に制限（取得範囲外を表示しようとする事故を防ぐ）。
        display_radius = st.number_input(
            "表示半径(km)", min_value=0.1, max_value=loaded_fetch_radius,
            value=loaded_fetch_radius, step=0.1,
        )

    # --- 企業一括ダウンロード（expander） ---
    # 取得済みDF全体（= 取得半径以内）を対象に、取得半径で出力する。
    company = loaded_company
    radius = loaded_fetch_radius
    with st.expander("企業一括ダウンロード", expanded=False):
        # 表示順: データダウンロード → 都道府県で絞り込み → 画像をダウンロード。
        # データ/画像は都道府県の選択値を使うため、コンテナで表示位置を固定しつつ
        # 先に都道府県を読み取る。
        data_box = st.container()
        pref_box = st.container()
        image_box = st.container()

        with pref_box:
            pref_opts = prefectures_for_company(df, company)
            prefs = st.multiselect(
                "都道府県で絞り込み", pref_opts, default=[],
                placeholder="都道府県を選択",
            )
            if prefs:
                count = store_count_for_company_prefectures(df, company, prefs)
                st.caption(f"選択中の都道府県: {count}件の店舗")

        # ファイル名に都道府県を付加
        pref_label = "_".join(sorted(prefs)) if prefs else ""
        csv_filename = (
            f"{company}_{pref_label}_{radius}km.csv"
            if pref_label
            else f"{company}_{radius}km.csv"
        )
        zip_filename = (
            f"{company}_{pref_label}_{radius}km.zip"
            if pref_label
            else f"{company}_{radius}km.zip"
        )

        # データダウンロード（単一CSV cp932・直接生成、都道府県選択時は絞込）
        with data_box:
            _csv = (
                filter_company(df, company, radius, prefectures=prefs if prefs else None)
                .to_csv(index=False)
                .encode("cp932", errors="replace")
            )
            st.download_button(
                "データダウンロード",
                data=_csv,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True,
            )

        # 画像をダウンロード（都道府県で絞込 → 1ボタンDL）
        with image_box:
            img_disabled = not prefs
            img_data = (
                _company_image_zip(df, company, tuple(sorted(prefs)), radius)
                if not img_disabled
                else b""
            )
            st.download_button(
                "画像をダウンロード",
                data=img_data,
                file_name=zip_filename,
                mime="application/zip",
                disabled=img_disabled,
                use_container_width=True,
            )

    st.divider()

    # --- 地図＋施設リスト ---
    # 表示は display_radius（取得済みデータをさらに絞り込む）で行う。
    if store is None:
        st.info("小売店名称を選択してください")
    else:
        srow = df[df["店舗名称"] == store].iloc[0]
        fac = filter_facilities(df, store, display_radius)

        # マップを誤って操作した場合に初期表示へ戻すリセット（紫帯の上に配置）。
        # st_folium の key を変えると再マウントされ、build_map の初期位置/ズームに戻る。
        if st.button("マップをリセット", key="reset_map"):
            st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
        nonce = st.session_state.get("map_nonce", 0)

        st.markdown(_header_html(store, display_radius), unsafe_allow_html=True)
        n = len(fac)
        if n == 0:
            st.warning("該当する推進園がありません")
        st.metric("対象推進園数", f"{n}件")
        col_map, col_list = st.columns([2, 1])
        with col_map:
            st_folium(
                build_map(srow, fac, display_radius),
                width=700,
                height=560,
                key=f"map_{store}_{display_radius}_{nonce}",
            )
        with col_list:
            st.markdown(_facility_list_html(fac), unsafe_allow_html=True)

    # --- 出典フッタ（小さく） ---
    _data_source_caption()
