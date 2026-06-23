"""
SC-02a: 企業一括データ抽出（単一CSV）

Public API
----------
render(df) -- render the page; df is the full master DataFrame.
"""

import logging

import pandas as pd
import streamlit as st

from lib.data import company_names, filter_company, filter_facilities

logger = logging.getLogger(__name__)

_HEADER_COLOR = "#7C3AED"


def _header_html(company: str, radius: float) -> str:
    return (
        f'<div style="'
        f"background-color:{_HEADER_COLOR};"
        f"color:#FFFFFF;height:64px;display:flex;align-items:center;"
        f"padding-left:24px;font-size:22px;font-weight:bold;"
        f"border-radius:8px;margin-bottom:12px;"
        f'">'
        f"{company} 一括データ抽出 ｜ 半径{radius}km圏内"
        f"</div>"
    )


def render(df) -> None:
    """Render SC-02a: company-level single-CSV data export."""
    company = st.sidebar.selectbox(
        "企業名称", company_names(df), index=None, placeholder="企業を選択してください"
    )
    radius = st.sidebar.number_input(
        "半径(km)", min_value=0.1, max_value=50.0, value=2.0, step=0.1
    )
    gen = st.sidebar.button("データ抽出")

    if company is None:
        st.info("左のサイドバーで企業と半径を指定してください")
        return

    st.markdown(_header_html(company, radius), unsafe_allow_html=True)

    sub = df[df["企業名称"] == company]
    names = sub["小売店名称"].unique().tolist()
    rows = []
    for name in names:
        code = sub[sub["小売店名称"] == name]["小売店コード"].iloc[0]
        count = len(filter_facilities(df, name, radius))
        rows.append({"小売店コード": code, "小売店名称": name, "対象推進園数": count})
    summary_df = pd.DataFrame(rows, columns=["小売店コード", "小売店名称", "対象推進園数"])
    st.dataframe(summary_df, use_container_width=True)

    if gen:
        data = filter_company(df, company, radius)
        csv = data.to_csv(index=False).encode("cp932", errors="replace")
        st.session_state["bulk_data"] = {"company": company, "radius": radius, "csv": csv}
        logger.info("SC-02a: csv rows=%d company=%s radius=%.1f", len(data), company, radius)

    bd = st.session_state.get("bulk_data")
    if bd is not None and bd["company"] == company and bd["radius"] == radius:
        st.download_button(
            "データをダウンロード",
            data=bd["csv"],
            file_name=f"{company}_{radius}km.csv",
            mime="text/csv",
        )
