"""
Entrypoint for 店舗周辺マップ (Databricks Apps / Streamlit).

Navigation
----------
SC-01   店舗周辺マップ          -> views/map_single.py
SC-02a  企業一括データ抽出      -> views/bulk_data.py
SC-02b  企業一括画像抽出        -> views/bulk_image.py
SC-03   ヘルプ                 -> views/help.py
"""

import logging

import streamlit as st

from lib.data import load_master
from views import map_single, bulk_data, bulk_image
from views import help as help_page

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
        ["店舗周辺マップ", "企業一括データ抽出", "企業一括画像抽出", "ヘルプ"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()

    if nav == "店舗周辺マップ":
        map_single.render(df)
    elif nav == "企業一括データ抽出":
        bulk_data.render(df)
    elif nav == "企業一括画像抽出":
        bulk_image.render(df)
    else:
        help_page.render(df)


if __name__ == "__main__":
    main()
