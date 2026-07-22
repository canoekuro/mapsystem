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

from lib.app_config import show_theme_page
from lib.data import load_company_names, load_table_last_updated
from views import config_page, main_page, upload_page

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
    # キャプションと同じ行の右側に、ページ側のアクション（例: マップをリセット）を横並びで
    # 置けるよう列を確保する。2列目のコンテナを session_state 経由でページへ渡し、縦の余白を
    # 1行分詰める。該当アクションが無いページ・状態では右列は空のまま（見た目に影響なし）。
    col_caption, col_action = st.columns([4, 1], vertical_alignment="center")
    col_caption.caption(text)
    st.session_state["_top_action_slot"] = col_action


def _map_page() -> None:
    try:
        companies = load_company_names()
    except Exception as e:  # noqa: BLE001
        st.error(f"企業名称の取得に失敗しました: {e}")
        return
    main_page.render(companies)


def _upload_page() -> None:
    upload_page.render()


def _config_page() -> None:
    config_page.render()


def _tighten_top_spacing() -> None:
    """メインコンテナ上部の余白を詰めて、全体を少し上に寄せる。

    Streamlit 既定の .block-container は上パディングが大きく、「データ最終更新」表記の
    上に空白ができてしまうため、padding-top を縮める（見た目のみの調整）。
    """
    st.markdown(
        "<style>"
        "[data-testid='stMainBlockContainer'],"
        "[data-testid='stAppViewBlockContainer'],"
        ".block-container{padding-top:1.5rem;}"
        "</style>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="店舗周辺マップ", layout="wide")
    _tighten_top_spacing()
    _render_last_updated()  # 共通: 両ページの上部に表示
    pages = [
        st.Page(_map_page, title="マップ", default=True),
        st.Page(_upload_page, title="データ更新"),
    ]
    # 「テーマ設定」ページは config/app_config.toml [ui] show_theme_page で出し分け（既定は非表示）。
    if show_theme_page():
        pages.append(st.Page(_config_page, title="テーマ設定"))
    nav = st.navigation(pages)
    nav.run()


if __name__ == "__main__":
    main()
