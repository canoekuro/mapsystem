"""
Entrypoint for 店舗周辺マップ (Databricks Apps / Streamlit).

Multipage:
- マップ: company/store/radius selection, company-bulk downloads, map + facility
  list, and a small data-source footer. Data is fetched on demand (only distinct
  company names load at startup).
- データ更新: upload 推進園/店舗 Excel files to a Unity Catalog Volume.

The upload page does not depend on the Databricks table query, so it stays usable
even if company-name loading fails.
"""

import logging

import streamlit as st

from lib.data import load_company_names
from views import main_page, upload_page

logging.basicConfig(level=logging.INFO)


def _map_page() -> None:
    try:
        companies = load_company_names()
    except Exception as e:  # noqa: BLE001
        st.error(f"企業名称の取得に失敗しました: {e}")
        return
    main_page.render(companies)


def _upload_page() -> None:
    upload_page.render()


def main() -> None:
    st.set_page_config(page_title="店舗周辺マップ", layout="wide")
    nav = st.navigation(
        [
            st.Page(_map_page, title="マップ", default=True),
            st.Page(_upload_page, title="データ更新"),
        ]
    )
    nav.run()


if __name__ == "__main__":
    main()
