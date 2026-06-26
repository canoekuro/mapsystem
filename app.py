"""
Entrypoint for 店舗周辺マップ (Databricks Apps / Streamlit).

Single page: company/store/radius selection, company-bulk downloads, map +
facility list, and a small data-source footer.

Data is fetched on demand: only distinct company names load at startup; the
filtered rows are pulled from Databricks when the user presses データ取得.
"""

import logging

import streamlit as st

from lib.data import load_company_names
from views import main_page

logging.basicConfig(level=logging.INFO)


def main() -> None:
    st.set_page_config(page_title="店舗周辺マップ", layout="wide")
    try:
        companies = load_company_names()
    except Exception as e:
        st.error(f"企業名称の取得に失敗しました: {e}")
        st.stop()
    main_page.render(companies)


if __name__ == "__main__":
    main()
