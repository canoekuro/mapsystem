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
    load_shipment_period,
    load_stores,
    load_table_last_updated_ts,
    stores_for_company,
    filter_facilities,
    prefectures_for_company,
    stores_for_company_prefectures,
    store_nursery_counts,
)
from lib.map_builder import build_map
from lib.pptx_builder import (
    build_store_pptx,
    load_caption,
    load_dated_caption,
    load_template_bytes,
)
from lib.static_map import render_static_map
from lib.zip_builder import build_pptx_zip

logger = logging.getLogger(__name__)

# ページ遷移（st.navigation）を跨いで保持する入力ウィジェットの session_state キー。
# 企業名称・取得半径・都道府県（表示行）・小売店名称。
_INPUT_KEYS = ("mp_company", "mp_fetch_radius", "mp_pref", "mp_store")


# df is excluded from the cache key (hash_funcs returns None): the store's map is
# uniquely determined by (store, radius, width, height) within the already-fetched df.
@st.cache_data(show_spinner="地図を生成中...", hash_funcs={pd.DataFrame: lambda _df: None})
def _store_map_png(df: pd.DataFrame, store: str, radius: float, width: int, height: int) -> bytes:
    # 対話地図（build_map）と体裁を合わせるため map_width×map_height で生成する
    # （issue 202607221245）。width/height はキャッシュキーに含める。
    srow = df[df["店舗名称"] == store].iloc[0]
    fac = filter_facilities(df, store, radius)
    return render_static_map(srow, fac, radius, width=width, height=height)


# 商談用資料 / 店舗POP の pptx。地図PNG（_store_map_png）を使い回し、テンプレ種別ごとに
# プレースホルダーへの貼り付けだけを行う（サーバ側の地図生成は店舗ごとに1回）。
# captions はテキストプレースホルダーへ入れる定型文（小売店名称・地図/店舗状況の時点・啓発活動年,
# issue 202607221450 / 202607221705）。呼び出し側で組み立てた tuple をそのままキャッシュキーに
# 含めるため、店舗やデータ更新日時が変わればデッキも作り直される。
@st.cache_data(show_spinner="資料を生成中...")
def _store_pptx(map_png: bytes, kind: str, captions: tuple[str, ...]) -> bytes:
    return build_store_pptx(load_template_bytes(kind), map_png, list(captions))


def _safe_last_updated_ts():
    """データ最終更新の JST Timestamp を返す（取得失敗時は None）。

    Databricks 未接続・参照不可でも pptx 生成を止めないため、例外は握りつぶして None を返す。
    """
    try:
        return load_table_last_updated_ts()
    except Exception as e:  # noqa: BLE001
        logger.warning("データ更新日時の取得に失敗: %s", e)
        return None


def _store_captions(store: str | None) -> tuple[str, ...]:
    """テキストプレースホルダー用の定型文3種を idx 昇順に対応する順で組み立てる。

    データ更新日時が取れないとき、日付入りの2種は空文字となり該当枠へは挿入されない。
    """
    ts = _safe_last_updated_ts()
    return (
        load_caption(store),
        load_dated_caption("map_status_caption_format", ts),
        load_dated_caption("activity_caption_format", ts),
    )


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


# 施設リストは 1 列あたり最大この件数を並べ、超過分は列を増やす（issue image3 で 10→8）。
_FACILITY_LIST_PER_COLUMN = 8
# 帯（施設リスト）の見せ幅にあたる初期表示列数。これを超える列は横スクロールで表示。
# 帯・ボディは col_list 全幅（width:100%）にし、各列はこの列数で等分（= 100/列数 %）してフィル
# する（issue image3「帯を上の帯と右端そろえ、2 列の幅も広げる」）。
_FACILITY_LIST_COLUMNS = 2
# 施設リスト列（col_list）の st.columns 比率ウェイト。帯の px 幅ではなく、マップ列との
# 面積比の基準として使う（image2「マップ–施設リスト間の余白を詰める」の挙動を保持）。
_FACILITY_LIST_COL_WEIGHT = 500


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
        f'<div style="font-size:12px;color:#6B7280;">約{distance:.1f}km</div>'
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
    """施設リストを 8 件/列で複数列に並べ、初期表示は 2 列（帯幅を等分）で 3 列目以降は横スクロール。"""
    # 帯・ボディとも col_list 全幅（width:100%）にし、上の「周辺マップ概要」帯と右端をそろえる
    # （issue image3「この帯の幅揃えたい」）。上に少し余白（image2「もうちょっと隙間開けたい」）。
    header = (
        '<div style="'
        f"background-color:{band_color()};"
        "color:#FFFFFF;height:40px;display:flex;align-items:center;"
        "justify-content:center;font-size:16px;font-weight:bold;"
        "border-radius:4px 4px 0 0;"
        "width:100%;margin-top:12px;"
        '">'
        "施設リスト"
        "</div>"
    )

    rows = list(fac.iterrows())
    # 8 件ごとに列へ分割。各列は帯幅を _FACILITY_LIST_COLUMNS で等分した幅（= 50%）でフィルし、
    # 名称欄を広げる（issue image3「2 列の幅も広げる」）。min-width:0 で名称の ellipsis を維持。
    # 罫線（列区切り線）は無し（issue image2）。
    col_basis = f"{100 / _FACILITY_LIST_COLUMNS:.4f}%"
    columns_html: list[str] = []
    for start in range(0, len(rows), _FACILITY_LIST_PER_COLUMN):
        chunk = rows[start : start + _FACILITY_LIST_PER_COLUMN]
        cards = "".join(_facility_card_html(row) for _, row in chunk)
        columns_html.append(
            '<div style="'
            f"flex:0 0 {col_basis};min-width:0;"
            '">'
            f"{cards}"
            "</div>"
        )

    # ボディも全幅。列群の合計が帯幅（＝2 列ぶん）を超えたら（＝3 列以上で）横スクロールで到達する。
    body = (
        '<div style="display:flex;overflow-x:auto;width:100%;">'
        f"{''.join(columns_html)}"
        "</div>"
    )
    return header + body


# --- part6: 出荷実績（当年実績(箱数)・前年比）テーブル ------------------------
# 選択中1店舗の出荷実績を image1.png 準拠の 2 値列（実績（箱数）/ 前年比（%））で表示する。
# 値は load_filtered の店舗行（srow）から取り込む（issue 202607231113）。
# 商材ラベル = 列接頭辞（プラズマ計 / おい免 / ムテキッズ, lib.data.SALES_PRODUCTS）。
_SALES_PLACEHOLDER = "—"


def _fmt_boxes(value) -> str:
    """実績（箱数）の表示。DB値をそのまま表示し、欠損は ``—``（issue 202607231113）。"""
    if value is None or pd.isna(value):
        return _SALES_PLACEHOLDER
    return f"{value}"


def _fmt_yoy(value) -> str:
    """前年比の表示。DB は比率（例 1.053）なので ×100 して小数1桁＋``%``。欠損は ``—``。"""
    if value is None or pd.isna(value):
        return _SALES_PLACEHOLDER
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return _SALES_PLACEHOLDER


def _sales_table_html(srow, period: str | None) -> str:
    """選択店舗 *srow* の出荷実績テーブル HTML を返す（実績（箱数）/ 前年比（%））。

    *period* は出荷実績の対象期間文字列（``lib.data.load_shipment_period``）。None のときは
    ``—`` を表示する。
    """
    from lib.data import SALES_PRODUCTS, sales_column  # noqa: PLC0415

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
        f'padding:6px 8px;font-size:13px;font-weight:bold;color:#111827;">{product}</td>'
        f'<td style="background:{cell_bg};border:1px solid {border};'
        'padding:6px 8px;font-size:13px;text-align:center;color:#111827;">'
        f'{_fmt_boxes(srow.get(sales_column(product, "当年実績（箱数）")))}</td>'
        f'<td style="background:{cell_bg};border:1px solid {border};'
        'padding:6px 8px;font-size:13px;text-align:center;color:#111827;">'
        f'{_fmt_yoy(srow.get(sales_column(product, "前年比")))}</td>'
        "</tr>"
        for product in SALES_PRODUCTS
    )
    period_text = period or _SALES_PLACEHOLDER
    return (
        '<div style="margin-top:12px;">'
        '<table style="border-collapse:collapse;width:100%;">'
        f"{header}{body_rows}"
        "</table>"
        '<div style="font-size:12px;color:#6B7280;margin-top:4px;text-align:right;">'
        f"出荷実績　期間：{period_text}"
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

    # --- 取得行（sidebar・常時表示）: 企業 + 取得半径 + データ取得ボタン ---
    # 選択フィルタは sidebar に集約し、ダウンロードの上に配置する（issue 202607221414）。
    with st.sidebar:
        st.markdown("### 検索条件")
        company = st.selectbox(
            "企業名称", companies, index=None, placeholder="企業を選択してください",
            key="mp_company",
        )
        fetch_radius = st.number_input(
            "取得半径(km)", min_value=1, max_value=None,
            value=None, step=1, format="%d", placeholder="半径を入力",
            key="mp_fetch_radius",
        )
        fetch_disabled = company is None or fetch_radius is None
        fetch_clicked = st.button(
            "データ取得", disabled=fetch_disabled, use_container_width=True, type="primary"
        )

    # データ取得: 企業 + 取得半径で Databricks 側を絞り込んで取得し、session_state に保存。
    if fetch_clicked:
        # 店舗×推進園（距離で絞る）と 小売店マスタ（距離で絞らない）の2つを取得する。
        # 前者はマップ・施設リスト、後者は選択肢・下部集計表の土台（issue 202607221128）。
        st.session_state["loaded_df"] = load_filtered(company, fetch_radius)
        st.session_state["loaded_stores_df"] = load_stores(company)
        st.session_state["loaded_company"] = company
        st.session_state["loaded_fetch_radius"] = fetch_radius

    # 未取得なら案内のみ表示して終了。
    if "loaded_df" not in st.session_state:
        st.info("企業名称と取得半径を入力して「データ取得」を押してください")
        _data_source_caption()
        return

    df = st.session_state["loaded_df"]
    stores_df = st.session_state["loaded_stores_df"]
    loaded_company = st.session_state["loaded_company"]
    loaded_fetch_radius = st.session_state["loaded_fetch_radius"]

    # 選択肢になる店舗数は小売店マスタ（距離非依存）から数える。圏内推進園0件の店舗も
    # 候補・集計表に残るため、ここは取得半径に依存しない（issue 202607221128）。
    # 取得店舗数の件数表示は廃止（issue 202607221414）。0件時の案内のみ残す。
    n_stores = stores_df["店舗名称"].nunique() if len(stores_df) else 0
    if n_stores == 0:
        st.warning(
            f"取得店舗数: 0件 — {loaded_company} の小売店データが取得できませんでした"
            "（取得処理は成功しています）"
        )

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

    # 小売店マスタが空（企業に店舗が無い）ならマップは表示せず 0 件アラートのみ
    # （issue 202607221128: 「データが無い場合はマップを表示せず0件をアラート」）。
    if n_stores == 0:
        _data_source_caption()
        return

    # --- 表示行（sidebar・取得後のみ）: 都道府県 + 小売店 ---
    # 選択フィルタは sidebar に集約する（issue 202607221414）。取得行の下・ダウンロードの上。
    # 絞り込み順は 企業 → 取得半径 →（データ取得）→ 都道府県 → 小売店名称。
    # 選択肢は小売店マスタ（stores_df）から生成し、圏内推進園0件の店舗も候補に含める。
    # 都道府県は単一選択・任意で、未選択なら企業内の全店舗を候補にする。
    with st.sidebar:
        pref_opts_disp = prefectures_for_company(stores_df, loaded_company)
        # 保持値が現在の候補に無ければクリア（options 変化時の例外回避）。
        if st.session_state.get("mp_pref") not in pref_opts_disp:
            st.session_state.pop("mp_pref", None)
        pref = st.selectbox(
            "都道府県", pref_opts_disp,
            index=None, placeholder="都道府県で絞り込み（任意）",
            key="mp_pref",
        )
        store_opts = (
            stores_for_company_prefectures(stores_df, loaded_company, [pref])
            if pref
            else stores_for_company(stores_df, loaded_company)
        )
        # 都道府県変更等で保持した店舗が候補外になった場合はクリア。
        if st.session_state.get("mp_store") not in store_opts:
            st.session_state.pop("mp_store", None)
        store = st.selectbox(
            "小売店名称", store_opts,
            index=None, placeholder="店舗を選択してください",
            key="mp_store",
        )

    # 選択中1店舗の地図PNG（商談用資料/店舗POP pptx 用）。店舗未選択・圏内0件では None。
    # sidebar のダウンロードボタンで使用する（issue 202607221245）。
    selected_map_png: bytes | None = None

    # --- 地図＋施設リスト ---
    # 表示半径は廃止し、取得半径（loaded_fetch_radius）をそのまま表示に用いる。
    store_rows = df[df["店舗名称"] == store] if store is not None else df.iloc[0:0]
    if store is None:
        st.info("小売店名称を選択してください")
    elif store_rows.empty:
        # 小売店マスタには在るが、取得半径圏内の推進園が0件で店舗×推進園DFに行が無い。
        # 店舗座標が取れずマップを描けないため、0件アラートのみ表示（issue 202607221128）。
        st.markdown(_header_html(store, loaded_fetch_radius), unsafe_allow_html=True)
        st.warning(
            f"半径{loaded_fetch_radius}km圏内に推進園が0件です（マップは表示されません）"
        )
    else:
        srow = store_rows.iloc[0]
        fac = filter_facilities(df, store, loaded_fetch_radius)

        # マップは固定画面（拡大縮小・移動を無効化, build_map）。誤操作でズレないため
        # 「マップをリセット」ボタンは廃止した。
        st.markdown(_header_html(store, loaded_fetch_radius), unsafe_allow_html=True)
        n = len(fac)
        if n == 0:
            st.warning("該当する推進園がありません")
        # マップは固定サイズ（map_width×map_height）。施設リストは col_list 全幅（帯・2 列とも）。
        # 列比をマップ幅 : 施設リスト列ウェイトに合わせ、両者の間の余白を最小化する
        # （issue image2「ここの隙間もっと狭めたい」）。
        col_map, col_list = st.columns(
            [map_width(), _FACILITY_LIST_COL_WEIGHT], gap="small"
        )
        with col_map:
            # 対象推進園数はマップ上（左）に配置し、施設リストを帯直下へ寄せる（part3）。
            st.metric("対象推進園数", f"{n}件")
            st_folium(
                build_map(srow, fac, loaded_fetch_radius),
                width=map_width(),
                height=map_height(),
                key=f"map_{store}_{loaded_fetch_radius}",
            )
            # 商談用資料 / 店舗POP の pptx 用に、対話地図と同寸（map_width×map_height）の
            # 地図PNGを1回だけ生成し sidebar のボタンで使い回す（issue 202607221245）。
            selected_map_png = _store_map_png(
                df, store, loaded_fetch_radius, map_width(), map_height()
            )
        with col_list:
            st.markdown(_facility_list_html(fac), unsafe_allow_html=True)
            # 施設リストの下に選択店舗の出荷実績（当年実績（箱数）・前年比・対象期間）を表示（part6）。
            st.markdown(
                _sales_table_html(srow, load_shipment_period()),
                unsafe_allow_html=True,
            )

    # --- 店舗別 推進園数サマリ ---
    # 小売店マスタ（企業全体の全店舗）に、取得半径圏内の推進園数を left join。圏内0件の
    # 店舗も 推進園数=0 で残る（issue 202607221128）。表はここに表示し、ダウンロードは sidebar。
    summary = store_nursery_counts(stores_df, df)
    st.markdown("##### 店舗別 推進園数")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    summary_csv = summary.to_csv(index=False).encode("cp932", errors="replace")

    # --- 出典フッタ（店舗別 推進園数表の下, issue 202607221414）---
    _data_source_caption()

    # --- ダウンロード（sidebar へ集約, issue 202607221245）---
    _render_sidebar_downloads(
        company=loaded_company,
        radius=loaded_fetch_radius,
        store=store,
        summary_csv=summary_csv,
        map_png=selected_map_png,
    )


def _render_sidebar_downloads(
    company: str,
    radius: float,
    store: str | None,
    summary_csv: bytes,
    map_png: bytes | None,
) -> None:
    """ダウンロード系ボタンを sidebar にまとめて配置する（issue 202607221245）。

    店舗別推進園数は企業全体（取得半径以内）が対象。商談用資料・店舗POP は選択中の1店舗が
    対象で、店舗未選択／圏内推進園0件（*map_png* が None）のときは無効化する。
    ローデータダウンロードは廃止した（issue 202607221414）。
    """
    with st.sidebar:
        st.markdown("### ダウンロード")
        st.download_button(
            "店舗別推進園数ダウンロード",
            data=summary_csv,
            file_name=f"{company}_{radius}km_店舗別推進園数.csv",
            mime="text/csv",
            use_container_width=True,
        )

        pptx_disabled = map_png is None
        if pptx_disabled:
            st.caption("小売店を選択すると商談資料・店舗POPを出力できます")
        # 商談用資料・店舗POP は両方DLするユースケースが大半のため1ボタンに統合し、
        # 押下で両pptxを1つのZIPにまとめてDLする（issue 202607231301）。
        # 定型文（データ更新日時を含む）は両テンプレ共通。ここで一度だけ組み立てる。
        captions = () if pptx_disabled else _store_captions(store)
        if pptx_disabled:
            zip_bytes = b""
        else:
            zip_bytes = build_pptx_zip(
                {
                    f"{store}_商談用資料.pptx": _store_pptx(map_png, "shoudan", captions),
                    f"{store}_店舗POP.pptx": _store_pptx(map_png, "pop", captions),
                }
            )
        st.download_button(
            "商談資料・店舗POPダウンロード",
            data=zip_bytes,
            file_name=f"{store}_商談資料・店舗POP.zip",
            mime="application/zip",
            disabled=pptx_disabled,
            use_container_width=True,
        )
