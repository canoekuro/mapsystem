"""
本部担当用ページ（issue 202607231301）。

企業G名称と取得半径を指定して「データ取得」を押すと、企業G配下の店舗別 推進園数
（圏内0件の店舗も 0 で残す）の表をメインに表示し、CSV でダウンロードできる。企業Gは
複数企業を跨ぐため表には企業名称列を含める。マップ・施設リスト・出荷実績テーブル・pptx
出力は持たない（店舗担当用ページとの役割分担）。

Public API
----------
render(groups) -- render the 本部担当用 page.
"""

import logging

import streamlit as st

from lib.data import (
    load_filtered_by_group,
    load_stores_by_group,
    store_nursery_counts,
)
from views.main_page import _data_source_caption

logger = logging.getLogger(__name__)

# ページ遷移（st.navigation）を跨いで保持する入力ウィジェットの session_state キー。
_INPUT_KEYS = ("hq_group", "hq_fetch_radius")


def render(groups: list[str]) -> None:
    """Render the 本部担当用 page.

    *groups* is the list of distinct 企業G名称 (loaded at startup). The filtered
    DataFrame is fetched on demand when データ取得 is pressed and kept in
    st.session_state.
    """
    # ページ遷移で入力ウィジェットの状態が破棄されるのを防ぐ（main_page と同じ手当て）。
    for _k in _INPUT_KEYS:
        if _k in st.session_state:
            st.session_state[_k] = st.session_state[_k]

    # 保持した選択肢が現在の候補に無い場合はクリアする（options 変化時の例外回避）。
    if st.session_state.get("hq_group") not in groups:
        st.session_state.pop("hq_group", None)

    # --- 取得行（sidebar）: 企業G + 取得半径 + データ取得ボタン ---
    with st.sidebar:
        st.markdown("### 検索条件")
        group = st.selectbox(
            "企業G名称", groups, index=None, placeholder="企業Gを選択してください",
            key="hq_group",
        )
        fetch_radius = st.number_input(
            "取得半径(km)", min_value=1, max_value=None,
            value=None, step=1, format="%d", placeholder="半径を入力",
            key="hq_fetch_radius",
        )
        fetch_disabled = group is None or fetch_radius is None
        fetch_clicked = st.button(
            "データ取得", disabled=fetch_disabled, use_container_width=True, type="primary"
        )

    st.header("本部担当用")

    # データ取得: 企業G + 取得半径で Databricks 側を絞り込んで取得し、session_state に保存。
    if fetch_clicked:
        st.session_state["hq_loaded_df"] = load_filtered_by_group(group, fetch_radius)
        st.session_state["hq_loaded_stores_df"] = load_stores_by_group(group)
        st.session_state["hq_loaded_group"] = group
        st.session_state["hq_loaded_fetch_radius"] = fetch_radius

    # 未取得なら案内のみ表示して終了。
    if "hq_loaded_df" not in st.session_state:
        st.info("企業G名称と取得半径を入力して「データ取得」を押してください")
        _data_source_caption()
        return

    df = st.session_state["hq_loaded_df"]
    stores_df = st.session_state["hq_loaded_stores_df"]
    loaded_group = st.session_state["hq_loaded_group"]
    loaded_fetch_radius = st.session_state["hq_loaded_fetch_radius"]

    n_stores = stores_df["店舗名称"].nunique() if len(stores_df) else 0
    if n_stores == 0:
        st.warning(
            f"取得店舗数: 0件 — {loaded_group} の小売店データが取得できませんでした"
            "（取得処理は成功しています）"
        )
        _data_source_caption()
        return

    # 現在の入力が取得済み条件と異なる場合は案内（旧データは表示し続ける）。
    changed = (group is not None and group != loaded_group) or (
        fetch_radius is not None and fetch_radius != loaded_fetch_radius
    )
    if changed:
        st.info(
            f"現在の入力（{group} / {fetch_radius}km）は取得済みデータ"
            f"（{loaded_group} / {loaded_fetch_radius}km）と異なります。"
            "「データ取得」を押すと再取得します。"
        )

    # --- 店舗別 推進園数サマリ（企業名称列を含む）---
    summary = store_nursery_counts(stores_df, df, include_company=True)
    st.markdown(f"##### 店舗別 推進園数（{loaded_group} ／ 半径{loaded_fetch_radius}km圏内）")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    summary_csv = summary.to_csv(index=False).encode("cp932", errors="replace")

    # --- 出典フッタ ---
    _data_source_caption()

    # --- ダウンロード（sidebar へ集約, 店舗担当用ページと体裁を合わせる）---
    with st.sidebar:
        st.markdown("### ダウンロード")
        st.download_button(
            "店舗別推進園数ダウンロード",
            data=summary_csv,
            file_name=f"{loaded_group}_{loaded_fetch_radius}km_店舗別推進園数.csv",
            mime="text/csv",
            use_container_width=True,
        )
