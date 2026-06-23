"""
Entrypoint for 店舗周辺マップ (Databricks Apps / Streamlit).

Navigation
----------
SC-01  店舗周辺マップ  -> pages/map_single.py
SC-02  企業一括出力    -> pages/map_bulk.py
SC-03  ヘルプ         -> pages/help.py
"""

import logging

import streamlit as st

from lib.data import load_master
from pages import map_single, map_bulk
from pages import help as help_page

logging.basicConfig(level=logging.INFO)


def main() -> None:
    st.set_page_config(page_title="店舗周辺マップ", layout="wide")

    # Master data load (SPEC §11)
    try:
        df = load_master()
    except Exception as e:
        st.error(f"マスタCSVの読込に失敗しました: {e}")
        st.stop()

    st.sidebar.title("店舗周辺マップ")
    nav = st.sidebar.radio(
        "ナビゲーション",
        ["店舗周辺マップ", "企業一括出力", "ヘルプ"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()

    if nav == "店舗周辺マップ":
        map_single.render(df)
    elif nav == "企業一括出力":
        map_bulk.render(df)
    else:
        help_page.render(df)


if __name__ == "__main__":
    main()
