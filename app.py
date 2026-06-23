"""
Entrypoint for 店舗周辺マップ (Databricks Apps / Streamlit).

Single page: company/store/radius selection, company-bulk downloads, map +
facility list, and a small data-source footer.
"""

import logging

import streamlit as st

from lib.data import load_master
from views import main_page

logging.basicConfig(level=logging.INFO)


def main() -> None:
    st.set_page_config(page_title="店舗周辺マップ", layout="wide")
    try:
        df = load_master()
    except Exception as e:
        st.error(f"マスタCSVの読込に失敗しました: {e}")
        st.stop()
    main_page.render(df)


if __name__ == "__main__":
    main()
