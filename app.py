"""
Entrypoint for 店舗周辺マップ (Databricks Apps / Streamlit).

Multipage:
- 店舗担当用: company/store/radius selection, company-bulk downloads, map + facility
  list, and a small data-source footer. Data is fetched on demand (only distinct
  company names load at startup).
- 本部担当用: 企業G/radius selection; shows the per-store nursery-count table for the
  whole company group (no map). Data is fetched on demand.
- データ更新: upload 推進園/店舗/RDP Excel files to a Unity Catalog Volume.

The upload page does not depend on the Databricks table query, so it stays usable
even if company-name loading fails.
"""

import logging

import streamlit as st

from lib.app_config import show_theme_page
from lib.data import (
    load_company_group_names,
    load_company_names,
    load_table_last_updated,
)
from views import config_page, hq_page, main_page, upload_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _render_last_updated() -> None:
    """Show the table's last data-update datetime (common to all pages)."""
    try:
        ts = load_table_last_updated()
    except Exception as e:  # noqa: BLE001
        logger.warning("テーブル更新日時の取得に失敗: %s", e)
        ts = None
    text = f"データ最終更新: {ts}（JST）" if ts else "データ最終更新: 取得できませんでした"
    # 更新日時は上部に右寄せで表示する（両ページ共通）。以前は左端にマップリセット用の
    # アクション列を確保していたが、マップを固定画面化してリセットボタンを廃止したため列分割は不要。
    st.markdown(
        f"<div style='text-align:right;color:#6B7280;font-size:0.875rem;'>{text}</div>",
        unsafe_allow_html=True,
    )


def _map_page() -> None:
    try:
        companies = load_company_names()
    except Exception as e:  # noqa: BLE001
        st.error(f"企業名称の取得に失敗しました: {e}")
        return
    main_page.render(companies)


def _hq_page() -> None:
    try:
        groups = load_company_group_names()
    except Exception as e:  # noqa: BLE001
        st.error(f"企業G名称の取得に失敗しました: {e}")
        return
    hq_page.render(groups)


def _upload_page() -> None:
    upload_page.render()


def _config_page() -> None:
    config_page.render()


def main() -> None:
    st.set_page_config(page_title="店舗周辺マップ", layout="wide")
    _render_last_updated()  # 共通: 両ページの上部に表示
    pages = [
        st.Page(_map_page, title="店舗担当用", default=True),
        st.Page(_hq_page, title="本部担当用"),
        st.Page(_upload_page, title="データ更新"),
    ]
    # 「テーマ設定」ページは config/app_config.toml [ui] show_theme_page で出し分け（既定は非表示）。
    if show_theme_page():
        pages.append(st.Page(_config_page, title="テーマ設定"))
    nav = st.navigation(pages)
    nav.run()


if __name__ == "__main__":
    main()
