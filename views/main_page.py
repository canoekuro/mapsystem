"""
単一ページ画面: 企業/小売店/半径の選択、データダウンロード、地図＋施設リスト、出典フッタ。

Public API
----------
render(df) -- render the whole single-page app.
"""

import logging

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from lib.colors import band_color, facility_color, map_height, map_width
from lib.data import (
    load_filtered,
    stores_for_company,
    filter_facilities,
    filter_company,
    prefectures_for_company,
    stores_for_company_prefectures,
    store_count_for_company_prefectures,
    store_nursery_counts,
)
from lib.map_builder import build_map
from lib.zip_builder import build_png_zip

logger = logging.getLogger(__name__)

# ページ遷移（st.navigation）を跨いで保持する入力ウィジェットの session_state キー。
# 企業名称・取得半径・都道府県（表示行）・小売店名称・都道府県（一括DL）。
_INPUT_KEYS = ("mp_company", "mp_fetch_radius", "mp_pref", "mp_store", "mp_prefs")


# df is excluded from the cache key (hash_funcs returns None): it is uniquely
# determined by the already-fetched (company, radius), which are part of the key.
@st.cache_data(show_spinner="画像を生成中...", hash_funcs={pd.DataFrame: lambda _df: None})
def _company_image_zip(df: pd.DataFrame, company: str, prefectures: tuple, radius: float) -> bytes:
    names = stores_for_company_prefectures(df, company, list(prefectures))
    return build_png_zip(df, names, radius)


def _header_html(store: str, radius: float) -> str:
    return (
        f'<div style="'
        f"background-color:{band_color()};"
        f"color:#FFFFFF;height:64px;display:flex;align-items:center;"
        f"padding-left:24px;font-size:22px;font-weight:bold;"
        f"border-radius:8px;margin-bottom:4px;"
        f'">'
        f"{store} 周辺マップ概要 ｜ 半径{radius}km圏内"
        f"</div>"
    )


# 施設リストは 1 列あたり最大この件数を並べ、超過分は列を増やす（issue 202607161811）。
_FACILITY_LIST_PER_COLUMN = 10
# 各列の固定幅（px）。名称が折り返さず収まるよう広めに取る（issue image2）。
# 帯・ボディの幅を 2 列ぶん（= _FACILITY_LIST_COLUMNS × この幅）に固定し、初期表示は 2 列
# ぴったり、3 列目以降は横スクロールで到達させる（issue image2）。
_FACILITY_COLUMN_WIDTH = 250
# 帯（施設リスト）の見せ幅にあたる初期表示列数。これを超える列は横スクロールで表示。
_FACILITY_LIST_COLUMNS = 2
# 帯・ボディの固定幅（px）＝ 初期表示 2 列ぶん。
_FACILITY_LIST_WIDTH = _FACILITY_COLUMN_WIDTH * _FACILITY_LIST_COLUMNS


def _facility_card_html(row) -> str:
    """施設リストの 1 行カード（番号バッジ + 名称 + 距離）の HTML を返す。"""
    color = facility_color(row["推進園区分"])
    number = int(row["連番"])
    name = row["推進園名称"]
    distance = row["距離km"]
    badge = (
        '<div style="'
        f"background-color:{color};"
        "color:#FFFFFF;width:24px;height:24px;border-radius:50%;"
        "display:flex;align-items:center;justify-content:center;"
        "font-size:11px;font-weight:bold;flex-shrink:0;"
        '">'
        f"{number}"
        "</div>"
    )
    # 名称は 1 行固定（折り返さず、はみ出しは末尾を「…」で省略）。ellipsis を効かせるため
    # info/name とも min-width:0 + overflow:hidden にする（issue image2「折り返しにならないように」）。
    info = (
        '<div style="margin-left:8px;min-width:0;overflow:hidden;">'
        f'<div style="font-size:14px;font-weight:bold;color:#111827;'
        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
        f"{name}</div>"
        f'<div style="font-size:12px;color:#6B7280;">約{distance:.2f}km</div>'
        "</div>"
    )
    # 罫線（カード下線）は削除（issue image2「枠線いらない」）。
    return (
        '<div style="'
        "display:flex;align-items:center;background-color:#FFFFFF;"
        "padding:8px 8px;"
        '">'
        f"{badge}{info}"
        "</div>"
    )


def _facility_list_html(fac) -> str:
    """施設リストを 10 件/列で複数列に並べ、初期表示は 2 列（帯幅）で 3 列目以降は横スクロール。"""
    # 帯・ボディとも幅を 2 列ぶんに固定し、上に少し余白を足す（issue image2「もうちょっと隙間開けたい」）。
    header = (
        '<div style="'
        f"background-color:{band_color()};"
        "color:#FFFFFF;height:40px;display:flex;align-items:center;"
        "justify-content:center;font-size:16px;font-weight:bold;"
        "border-radius:4px 4px 0 0;"
        f"width:{_FACILITY_LIST_WIDTH}px;max-width:100%;margin-top:12px;"
        '">'
        "施設リスト"
        "</div>"
    )

    rows = list(fac.iterrows())
    # 10 件ごとに列へ分割し、各列を固定幅の div にまとめる（罫線＝列区切り線は削除, issue image2）。
    columns_html: list[str] = []
    for start in range(0, len(rows), _FACILITY_LIST_PER_COLUMN):
        chunk = rows[start : start + _FACILITY_LIST_PER_COLUMN]
        cards = "".join(_facility_card_html(row) for _, row in chunk)
        columns_html.append(
            '<div style="'
            f"flex:0 0 auto;width:{_FACILITY_COLUMN_WIDTH}px;"
            '">'
            f"{cards}"
            "</div>"
        )

    # ボディ幅も 2 列ぶんに固定。列群がこの幅を超えたら（＝3 列以上で）横スクロールで到達する。
    body = (
        '<div style="display:flex;overflow-x:auto;'
        f"width:{_FACILITY_LIST_WIDTH}px;max-width:100%;"
        '">'
        f"{''.join(columns_html)}"
        "</div>"
    )
    return header + body


# --- part6: 出荷実績（当年実績ケース数・前年比）テーブル ---------------------
# NOTE: 実績・前年比の実データ源は未確定のため、現状は image1.png 準拠の「枠のみ」を
# ダミー表示する（issue 202607161811）。実データ接続時は下記 _SALES_ROWS を廃し、
# lib/data.py の新規データ源（店舗コード等をキーに結合）から値を差し込むこと。
_SALES_ROWS = ("プラズマ計", "おい免", "ムテキッズ")
_SALES_PLACEHOLDER = "—"


def _sales_table_html() -> str:
    """出荷実績（実績(箱数)/前年比(%)）のダミー枠テーブル HTML を返す。"""
    head_bg = "#31597A"      # image1 のヘッダー帯（濃紺）
    label_bg = "#E9EDF1"     # 行見出しの薄灰
    cell_bg = "#F5F7F9"
    border = "#D1D5DB"

    header = (
        "<tr>"
        f'<th style="background:{head_bg};border:1px solid {border};"></th>'
        f'<th style="background:{head_bg};color:#FFFFFF;border:1px solid {border};'
        'padding:6px 8px;font-size:13px;text-align:center;">実績（箱数）</th>'
        f'<th style="background:{head_bg};color:#FFFFFF;border:1px solid {border};'
        'padding:6px 8px;font-size:13px;text-align:center;">前年比（%）</th>'
        "</tr>"
    )
    body_rows = "".join(
        "<tr>"
        f'<td style="background:{label_bg};border:1px solid {border};'
        f'padding:6px 8px;font-size:13px;font-weight:bold;color:#111827;">{name}</td>'
        f'<td style="background:{cell_bg};border:1px solid {border};'
        f'padding:6px 8px;font-size:13px;text-align:center;color:#6B7280;">{_SALES_PLACEHOLDER}</td>'
        f'<td style="background:{cell_bg};border:1px solid {border};'
        f'padding:6px 8px;font-size:13px;text-align:center;color:#6B7280;">{_SALES_PLACEHOLDER}</td>'
        "</tr>"
        for name in _SALES_ROWS
    )
    return (
        '<div style="margin-top:12px;">'
        '<table style="border-collapse:collapse;width:100%;">'
        f"{header}{body_rows}"
        "</table>"
        '<div style="font-size:12px;color:#6B7280;margin-top:4px;text-align:right;">'
        "出荷実績　期間：—"
        "</div>"
        "</div>"
    )


def _data_source_caption() -> None:
    st.divider()
    st.caption(
        "データ出典: 位置参照情報（大字町丁目・街区レベル）令和6年（国土交通省）、"
        "電子国土基本図（地名情報）住居表示住所（国土地理院）、"
        "Geolonia 住所データ（株式会社Geolonia）"
        " [japanese-addresses](https://geolonia.github.io/japanese-addresses/)、"
        "アドレス・ベース・レジストリ（デジタル庁）"
        " [base_registry_address](https://www.digital.go.jp/policies/base_registry_address_tos/)、"
        "登記所備付地図データ（法務省）をもとに、株式会社情報試作室が加工した"
        " jageocoder 用住所データベース（住居表示レベル）を利用"
    )


def render(companies: list[str]) -> None:
    """Render the single-page app.

    *companies* is the list of distinct company names (loaded at startup).
    The filtered DataFrame is fetched on demand when データ取得 is pressed and
    kept in st.session_state.
    """
    # ページ遷移（st.navigation）で入力ウィジェットの状態が破棄されるのを防ぐ。
    # 各 widget キーを自身へ再代入し、他ページ表示中に purge されないようにする
    # （企業名称・取得半径・都道府県・小売店名称が戻ったときに復元される）。
    for _k in _INPUT_KEYS:
        if _k in st.session_state:
            st.session_state[_k] = st.session_state[_k]

    # 保持した選択肢が現在の候補に無い場合はクリアする（options 変化時の例外回避）。
    if st.session_state.get("mp_company") not in companies:
        st.session_state.pop("mp_company", None)

    # --- 取得行（常時表示）: 企業 + 取得半径 + データ取得ボタン ---
    g1, g2, g3 = st.columns([2, 1, 1])
    with g1:
        company = st.selectbox(
            "企業名称", companies, index=None, placeholder="企業を選択してください",
            key="mp_company",
        )
    with g2:
        fetch_radius = st.number_input(
            "取得半径(km)", min_value=1, max_value=None,
            value=None, step=1, format="%d", placeholder="半径を入力",
            key="mp_fetch_radius",
        )
    with g3:
        # ラベル高さ分のスペーサで selectbox/number_input と縦位置を揃える。
        st.write("")
        st.write("")
        fetch_disabled = company is None or fetch_radius is None
        fetch_clicked = st.button(
            "データ取得", disabled=fetch_disabled, use_container_width=True, type="primary"
        )

    # データ取得: 企業 + 取得半径で Databricks 側を絞り込んで取得し、session_state に保存。
    if fetch_clicked:
        st.session_state["loaded_df"] = load_filtered(company, fetch_radius)
        st.session_state["loaded_company"] = company
        st.session_state["loaded_fetch_radius"] = fetch_radius

    # 未取得なら案内のみ表示して終了。
    if "loaded_df" not in st.session_state:
        st.info("企業名称と取得半径を入力して「データ取得」を押してください")
        _data_source_caption()
        return

    df = st.session_state["loaded_df"]
    loaded_company = st.session_state["loaded_company"]
    loaded_fetch_radius = st.session_state["loaded_fetch_radius"]

    # --- 取得件数サマリ（取得後は常時表示）---
    # 0件のとき選択肢が空になるだけで取得失敗と区別できない問題を避けるため、
    # 選択肢になる店舗数を明示する（取得済みDFから都度算出）。
    n_stores = df["店舗名称"].nunique() if len(df) else 0
    if n_stores == 0:
        st.warning(
            f"取得店舗数: 0件 — {loaded_company} / 半径{loaded_fetch_radius}km に"
            "該当するデータがありませんでした（取得処理は成功しています）"
        )
    else:
        st.success(f"取得店舗数: {n_stores:,}件")

    # 現在の入力が取得済み条件と異なる場合は案内（旧データは表示し続ける）。
    changed = (company is not None and company != loaded_company) or (
        fetch_radius is not None and fetch_radius != loaded_fetch_radius
    )
    if changed:
        st.info(
            f"現在の入力（{company} / {fetch_radius}km）は取得済みデータ"
            f"（{loaded_company} / {loaded_fetch_radius}km）と異なります。"
            "「データ取得」を押すと再取得します。"
        )

    # --- データダウンロード（expander）: 小売店選択より上に配置 ---
    # 取得済みDF全体（= 取得半径以内）を対象に、取得半径で出力する。
    company = loaded_company
    radius = loaded_fetch_radius
    with st.expander("データダウンロード", expanded=False):
        # 表示順: ローデータダウンロード → 都道府県で絞り込み → 画像をダウンロード。
        # データ/画像は都道府県の選択値を使うため、コンテナで表示位置を固定しつつ
        # 先に都道府県を読み取る。
        data_box = st.container()
        pref_box = st.container()
        image_box = st.container()

        with pref_box:
            pref_opts = prefectures_for_company(df, company)
            # 保持値のうち現在の候補に無いものを除外（options 変化時の例外回避）。
            if "mp_prefs" in st.session_state:
                st.session_state["mp_prefs"] = [
                    p for p in st.session_state["mp_prefs"] if p in pref_opts
                ]
            prefs = st.multiselect(
                "都道府県で絞り込み", pref_opts, default=[],
                placeholder="都道府県を選択", key="mp_prefs",
            )
            if prefs:
                count = store_count_for_company_prefectures(df, company, prefs)
                st.caption(f"選択中の都道府県: {count}件の店舗")

        # ファイル名に都道府県を付加
        pref_label = "_".join(sorted(prefs)) if prefs else ""
        csv_filename = (
            f"{company}_{pref_label}_{radius}km.csv"
            if pref_label
            else f"{company}_{radius}km.csv"
        )
        zip_filename = (
            f"{company}_{pref_label}_{radius}km.zip"
            if pref_label
            else f"{company}_{radius}km.zip"
        )

        # ローデータダウンロード（単一CSV cp932・直接生成、都道府県選択時は絞込）
        with data_box:
            _csv = (
                filter_company(df, company, radius, prefectures=prefs if prefs else None)
                .to_csv(index=False)
                .encode("cp932", errors="replace")
            )
            st.download_button(
                "ローデータダウンロード",
                data=_csv,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True,
            )

        # 画像をダウンロード（都道府県で絞込 → 1ボタンDL）
        with image_box:
            img_disabled = not prefs
            img_data = (
                _company_image_zip(df, company, tuple(sorted(prefs)), radius)
                if not img_disabled
                else b""
            )
            st.download_button(
                "画像をダウンロード",
                data=img_data,
                file_name=zip_filename,
                mime="application/zip",
                disabled=img_disabled,
                use_container_width=True,
            )

    # --- 表示行（取得後のみ）: 都道府県 + 小売店 ---
    # 絞り込み順は 企業 → 取得半径 →（データ取得）→ 都道府県 → 小売店名称。
    # 都道府県は単一選択・任意で、未選択なら企業内の全店舗を候補にする。
    pref_col, store_col = st.columns([1, 2])
    with pref_col:
        pref_opts_disp = prefectures_for_company(df, loaded_company)
        # 保持値が現在の候補に無ければクリア（options 変化時の例外回避）。
        if st.session_state.get("mp_pref") not in pref_opts_disp:
            st.session_state.pop("mp_pref", None)
        pref = st.selectbox(
            "都道府県", pref_opts_disp,
            index=None, placeholder="都道府県で絞り込み（任意）",
            key="mp_pref",
        )
    with store_col:
        store_opts = (
            stores_for_company_prefectures(df, loaded_company, [pref])
            if pref
            else stores_for_company(df, loaded_company)
        )
        # 都道府県変更等で保持した店舗が候補外になった場合はクリア。
        if st.session_state.get("mp_store") not in store_opts:
            st.session_state.pop("mp_store", None)
        store = st.selectbox(
            "小売店名称", store_opts,
            index=None, placeholder="店舗を選択してください",
            key="mp_store",
        )

    st.divider()

    # --- 地図＋施設リスト ---
    # 表示半径は廃止し、取得半径（loaded_fetch_radius）をそのまま表示に用いる。
    if store is None:
        st.info("小売店名称を選択してください")
    else:
        srow = df[df["店舗名称"] == store].iloc[0]
        fac = filter_facilities(df, store, loaded_fetch_radius)

        # マップを誤って操作した場合に初期表示へ戻すリセット（紫帯の上に配置）。
        # st_folium の key を変えると再マウントされ、build_map の初期位置/ズームに戻る。
        if st.button("マップをリセット", key="reset_map"):
            st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
        nonce = st.session_state.get("map_nonce", 0)

        st.markdown(_header_html(store, loaded_fetch_radius), unsafe_allow_html=True)
        n = len(fac)
        if n == 0:
            st.warning("該当する推進園がありません")
        # マップは固定サイズ（map_width×map_height）のまま、施設リストは 2 列ぶんの固定幅。
        # 列比を各固定幅（マップ幅 : 施設リスト2列幅）の実 px に合わせ、両者の間の余白を最小化する
        # （issue image2「ここの隙間もっと狭めたい」）。
        col_map, col_list = st.columns(
            [map_width(), _FACILITY_LIST_WIDTH], gap="small"
        )
        with col_map:
            # 対象推進園数はマップ上（左）に配置し、施設リストを帯直下へ寄せる（part3）。
            st.metric("対象推進園数", f"{n}件")
            st_folium(
                build_map(srow, fac, loaded_fetch_radius),
                width=map_width(),
                height=map_height(),
                key=f"map_{store}_{loaded_fetch_radius}_{nonce}",
            )
        with col_list:
            st.markdown(_facility_list_html(fac), unsafe_allow_html=True)
            # 施設リストの下に出荷実績（当年実績ケース数・前年比）のダミー枠を表示（part6）。
            st.markdown(_sales_table_html(), unsafe_allow_html=True)

    # --- 出典フッタ（小さく） ---
    _data_source_caption()

    # --- 店舗別 推進園数サマリ（出典表示の下, part1）---
    # 取得済み DF（企業一致 & 距離km<=取得半径）を pandas 集計。企業全体の全店舗が対象。
    summary = store_nursery_counts(df)
    st.markdown("##### 店舗別 推進園数")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    _summary_csv = summary.to_csv(index=False).encode("cp932", errors="replace")
    st.download_button(
        "店舗別推進園数ダウンロード",
        data=_summary_csv,
        file_name=f"{loaded_company}_{loaded_fetch_radius}km_店舗別推進園数.csv",
        mime="text/csv",
        use_container_width=True,
    )
