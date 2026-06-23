"""
SC-01: 店舗周辺マップ画面（個別）

Public API
----------
render(df) -- render the page; df is the full master DataFrame.
"""

import logging

import streamlit as st
from streamlit_folium import st_folium

from lib.data import store_names, filter_facilities
from lib.map_builder import build_map
from lib.png_builder import build_png

logger = logging.getLogger(__name__)

# Facility category -> badge color (SPEC §6.1.2)
_FACILITY_COLORS: dict[str, str] = {
    "保育園": "#22C55E",
    "幼稚園": "#EF4444",
    "こども園": "#F59E0B",
}
_FALLBACK_COLOR = "#6B7280"

_HEADER_COLOR = "#7C3AED"


def _facility_color(category: str) -> str:
    return _FACILITY_COLORS.get(category, _FALLBACK_COLOR)


def _header_html(store: str, radius: float) -> str:
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
        f"{store} 周辺マップ概要 ｜ 半径{radius}km圏内"
        f"</div>"
    )


def _facility_list_html(fac) -> str:
    """Build a single HTML string with the facility-list header and cards."""
    parts: list[str] = []

    # List header bar
    parts.append(
        '<div style="'
        f"background-color:{_HEADER_COLOR};"
        "color:#FFFFFF;"
        "height:40px;"
        "display:flex;"
        "align-items:center;"
        "justify-content:center;"
        "font-size:16px;"
        "font-weight:bold;"
        "border-radius:4px 4px 0 0;"
        '">'
        "施設リスト"
        "</div>"
    )

    # Facility cards
    for _, row in fac.iterrows():
        category = row["施設区分"]
        color = _facility_color(category)
        number = int(row["連番"])
        name = row["施設名称"]
        distance = row["距離"]

        badge = (
            '<div style="'
            f"background-color:{color};"
            "color:#FFFFFF;"
            "width:24px;"
            "height:24px;"
            "border-radius:50%;"
            "display:flex;"
            "align-items:center;"
            "justify-content:center;"
            "font-size:11px;"
            "font-weight:bold;"
            "flex-shrink:0;"
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

        card = (
            '<div style="'
            "display:flex;"
            "align-items:center;"
            "background-color:#FFFFFF;"
            "border-bottom:1px solid #E5E7EB;"
            "padding:8px 8px;"
            '">'
            f"{badge}{info}"
            "</div>"
        )
        parts.append(card)

    return "\n".join(parts)


def render(df) -> None:
    """Render SC-01: single-store map page.

    Adds sidebar inputs below the divider drawn by app.py, then renders the
    main area.
    """
    # --- Sidebar inputs (SPEC §6.1.1) ---
    store = st.sidebar.selectbox(
        "小売店名称",
        store_names(df),
        index=None,
        placeholder="店舗を選択してください",
    )
    radius = st.sidebar.number_input(
        "半径(km)",
        min_value=0.1,
        max_value=50.0,
        value=2.0,
        step=0.1,
    )

    if st.sidebar.button("表示"):
        if store is None:
            st.sidebar.warning("店舗を選択してください")
            return

        srow = df[df["小売店名称"] == store].iloc[0]
        fac = filter_facilities(df, store, radius)

        with st.spinner("画像を生成中..."):
            png = build_png(srow, fac, radius)

        csv = fac.to_csv(index=False).encode("utf-8")

        st.session_state["single"] = {
            "store": store,
            "radius": radius,
            "srow": srow,
            "fac": fac,
            "png": png,
            "csv": csv,
        }
        logger.info("SC-01: computed for store=%s radius=%.1f n=%d", store, radius, len(fac))

    # --- Main area ---
    if "single" not in st.session_state:
        st.info("左のサイドバーで店舗と半径を指定し「表示」を押してください")
        return

    state = st.session_state["single"]
    store = state["store"]
    radius = state["radius"]
    srow = state["srow"]
    fac = state["fac"]
    png = state["png"]
    csv = state["csv"]

    # Header bar
    st.markdown(_header_html(store, radius), unsafe_allow_html=True)

    # Metric
    n = len(fac)
    if n == 0:
        st.warning("該当する推進園がありません")

    st.metric("対象推進園数", f"{n}件")

    # Two-column layout: map (left) + facility list (right)
    col_map, col_list = st.columns([2, 1])

    with col_map:
        st_folium(build_map(srow, fac, radius), width=700, height=560)

    with col_list:
        st.markdown(_facility_list_html(fac), unsafe_allow_html=True)

        # Download buttons inside col_list (below the list)
        st.download_button(
            "画像をダウンロード",
            data=png,
            file_name=f"{store}.png",
            mime="image/png",
        )
        st.download_button(
            "データをダウンロード",
            data=csv,
            file_name=f"{store}_{radius}km.csv",
            mime="text/csv",
        )
