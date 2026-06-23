"""
単一ページ画面: 企業/小売店/半径の選択、企業一括ダウンロード、地図＋施設リスト、出典フッタ。

Public API
----------
render(df) -- render the whole single-page app.
"""

import logging

import streamlit as st
from streamlit_folium import st_folium

from lib.data import (
    company_names,
    stores_for_company,
    filter_facilities,
    filter_company,
)
from lib.map_builder import build_map
from lib.zip_builder import build_png_zip

logger = logging.getLogger(__name__)

_FACILITY_COLORS = {"保育園": "#22C55E", "幼稚園": "#EF4444", "こども園": "#F59E0B"}
_FALLBACK_COLOR = "#6B7280"
_HEADER_COLOR = "#7C3AED"


def _facility_color(category: str) -> str:
    return _FACILITY_COLORS.get(category, _FALLBACK_COLOR)


def _header_html(store: str, radius: float) -> str:
    return (
        f'<div style="'
        f"background-color:{_HEADER_COLOR};"
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
        f"background-color:{_HEADER_COLOR};"
        "color:#FFFFFF;height:40px;display:flex;align-items:center;"
        "justify-content:center;font-size:16px;font-weight:bold;"
        "border-radius:4px 4px 0 0;"
        '">'
        "施設リスト"
        "</div>"
    )
    for _, row in fac.iterrows():
        color = _facility_color(row["施設区分"])
        number = int(row["連番"])
        name = row["施設名称"]
        distance = row["距離"]
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
            f'<div style="font-size:12px;color:#6B7280;">約{distance}km</div>'
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


def render(df) -> None:
    """Render the single-page app."""
    # --- 上部コントロール ---
    c1, c2, c3 = st.columns(3)
    with c1:
        company = st.selectbox(
            "企業名称", company_names(df), index=None, placeholder="企業を選択してください"
        )
    with c2:
        store_opts = stores_for_company(df, company) if company else []
        store = st.selectbox(
            "小売店名称", store_opts, index=None, placeholder="店舗を選択してください"
        )
    with c3:
        radius = st.number_input(
            "半径(km)", min_value=0.1, max_value=50.0, value=2.0, step=0.1
        )

    # --- 企業一括ダウンロード ---
    b1, b2 = st.columns(2)
    with b1:
        if company is not None:
            csv = (
                filter_company(df, company, radius)
                .to_csv(index=False)
                .encode("cp932", errors="replace")
            )
            csv_name = f"{company}_{radius}km.csv"
        else:
            csv = b""
            csv_name = "data.csv"
        st.download_button(
            "企業一括データダウンロード",
            data=csv,
            file_name=csv_name,
            mime="text/csv",
            disabled=company is None,
        )
    with b2:
        if st.button("企業一括画像を生成", disabled=company is None):
            names = stores_for_company(df, company)
            progress = st.progress(0.0)
            cb = lambda done, total: progress.progress(done / total)
            with st.spinner("画像ZIPを生成中..."):
                pzip = build_png_zip(df, names, radius, progress_cb=cb)
            st.session_state["bulk_image"] = {
                "company": company,
                "radius": radius,
                "pzip": pzip,
            }
            logger.info(
                "bulk image zip: company=%s radius=%.1f stores=%d",
                company,
                radius,
                len(names),
            )
        bi = st.session_state.get("bulk_image")
        if (
            bi is not None
            and company is not None
            and bi["company"] == company
            and bi["radius"] == radius
        ):
            st.download_button(
                "画像ZIPをダウンロード",
                data=bi["pzip"],
                file_name=f"{company}_{radius}km.zip",
                mime="application/zip",
            )

    st.divider()

    # --- 地図＋施設リスト ---
    if store is None:
        st.info("企業名称と小売店名称を選択してください")
    else:
        srow = df[df["小売店名称"] == store].iloc[0]
        fac = filter_facilities(df, store, radius)
        st.markdown(_header_html(store, radius), unsafe_allow_html=True)
        n = len(fac)
        if n == 0:
            st.warning("該当する推進園がありません")
        st.metric("対象推進園数", f"{n}件")
        col_map, col_list = st.columns([2, 1])
        with col_map:
            st_folium(build_map(srow, fac, radius), width=700, height=560)
        with col_list:
            st.markdown(_facility_list_html(fac), unsafe_allow_html=True)

    # --- 出典フッタ（小さく） ---
    _data_source_caption()
