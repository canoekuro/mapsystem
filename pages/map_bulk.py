"""
SC-02: 企業一括出力画面

Public API
----------
render(df) -- render the page; df is the full master DataFrame.
"""

import logging

import pandas as pd
import streamlit as st

from lib.data import company_names, filter_facilities
from lib.zip_builder import build_png_zip, build_csv_zip

logger = logging.getLogger(__name__)

_HEADER_COLOR = "#7C3AED"


def _header_html(company: str, radius: float) -> str:
    return (
        f'<div style="'
        f"background-color:{_HEADER_COLOR};"
        f"color:#FFFFFF;"
        f"height:64px;"
        f"display:flex;"
        f"align-items:center;"
        f"padding-left:24px;"
        f"font-size:22px;"
        f"font-weight:bold;"
        f"border-radius:8px;"
        f"margin-bottom:12px;"
        f'">'
        f"{company} 一括出力 ｜ 半径{radius}km圏内"
        f"</div>"
    )


def render(df) -> None:
    """Render SC-02: bulk (company-level) export page.

    Adds sidebar inputs below the divider drawn by app.py, then renders the
    main area.
    """
    # --- Sidebar inputs (SPEC §6.2.1) ---
    company = st.sidebar.selectbox(
        "企業名称",
        company_names(df),
        index=None,
        placeholder="企業を選択してください",
    )
    radius = st.sidebar.number_input(
        "半径(km)",
        min_value=0.1,
        max_value=50.0,
        value=2.0,
        step=0.1,
    )
    gen = st.sidebar.button("ZIP生成")

    # --- Main area ---
    if company is None:
        st.info("左のサイドバーで企業と半径を指定してください")
        return

    # Header bar
    st.markdown(_header_html(company, radius), unsafe_allow_html=True)

    # Store summary table
    sub = df[df["企業名称"] == company]
    names = sub["小売店名称"].unique().tolist()

    rows = []
    for name in names:
        store_rows = sub[sub["小売店名称"] == name]
        code = store_rows["小売店コード"].iloc[0]
        count = len(filter_facilities(df, name, radius))
        rows.append({"小売店コード": code, "小売店名称": name, "対象推進園数": count})

    summary_df = pd.DataFrame(rows, columns=["小売店コード", "小売店名称", "対象推進園数"])
    st.dataframe(summary_df, use_container_width=True)

    # ZIP generation
    if gen:
        progress = st.progress(0.0)
        cb = lambda done, total: progress.progress(done / total)

        with st.spinner("画像ZIPを生成中..."):
            pzip = build_png_zip(df, names, radius, progress_cb=cb)

        czip = build_csv_zip(df, names, radius)
        logger.info(
            "SC-02: built ZIP for company=%s radius=%.1f stores=%d",
            company,
            radius,
            len(names),
        )

        st.session_state["bulk"] = {
            "company": company,
            "radius": radius,
            "pzip": pzip,
            "czip": czip,
        }

    # Download buttons (show when session_state matches current selection)
    bulk = st.session_state.get("bulk")
    if (
        bulk is not None
        and bulk["company"] == company
        and bulk["radius"] == radius
    ):
        pzip = bulk["pzip"]
        czip = bulk["czip"]

        st.download_button(
            "ZIPをダウンロード",
            data=pzip,
            file_name=f"{company}_{radius}km.zip",
            mime="application/zip",
        )
        st.download_button(
            "データZIPをダウンロード",
            data=czip,
            file_name=f"{company}_{radius}km_data.zip",
            mime="application/zip",
        )
