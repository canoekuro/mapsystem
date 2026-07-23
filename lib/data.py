"""
Data access helpers — reads master data from Databricks Unity Catalog.

Functions
---------
load_company_names()                   -- cached lightweight distinct 企業名称 loader
load_company_group_names()             -- cached lightweight distinct 企業G名称 loader (本部担当用)
load_filtered()                        -- fetch one company within fetch radius (Spark-side filter)
load_filtered_by_group()               -- fetch one 企業G within fetch radius (本部担当用)
load_stores()                          -- fetch the store master for one company (no radius filter)
load_stores_by_group()                 -- fetch the store master for one 企業G (本部担当用)
load_shipment_period()                 -- 出荷実績の対象期間文字列（rdp_update.toml から）
store_names(df)                        -- unique store names (sorted)
company_names(df)                      -- unique company names (sorted)
filter_facilities()                    -- filter by store + radius, add 連番
filter_company()                       -- filter by company + radius (for single-file export)
store_count_for_company_prefectures()  -- store count for company + prefecture selection
zoom_for_radius()                      -- zoom level that keeps the radius circle in view
"""

import logging
import math
import re
import tomllib

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

_COLUMN_MAPPING_PATH = "config/column_mapping.toml"
_DATABRICKS_CONFIG_PATH = "config/databricks_config.toml"

# 出荷実績（3商材 × 3指標）の列（アプリ内部名＝テーブル列名, issue 202607231113）。
# マップ画面の出荷実績テーブル・店舗別 推進園数テーブルで共有する。
SALES_PRODUCTS = ("プラズマ計", "おい免", "ムテキッズ")
SALES_METRICS = ("当年実績（箱数）", "前年実績（箱数）", "前年比")


def sales_column(product: str, metric: str) -> str:
    """商材名と指標名から実績列名（例: ``プラズマ計_前年比``）を組み立てる。"""
    return f"{product}_{metric}"


# 実績9列の一覧（商材ごとに 当年実績 → 前年実績 → 前年比 の順）。
SALES_COLUMNS: list[str] = [
    sales_column(p, m) for p in SALES_PRODUCTS for m in SALES_METRICS
]


def _load_column_mapping() -> dict[str, str]:
    """Load app_column_name -> table_column_name mapping from config/column_mapping.toml."""
    try:
        with open(_COLUMN_MAPPING_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("columns", {})
    except FileNotFoundError:
        return {}


def _load_databricks_config() -> dict:
    """Load Databricks connection config from config/databricks_config.toml."""
    try:
        with open(_DATABRICKS_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("databricks", {})
    except FileNotFoundError:
        return {}


def _load_rdp_config() -> dict:
    """Load the [rdp] section from config/databricks_config.toml (出荷実績期間ファイル)."""
    try:
        with open(_DATABRICKS_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("rdp", {})
    except FileNotFoundError:
        return {}


# 出荷実績期間ファイルの「（開始 ～ 終了）」を取り出す正規表現（全角/半角の波ダッシュ両対応）。
# 値がクォートされておらず TOML として不正なため tomllib ではなく正規表現で解析する。
_PERIOD_RE = re.compile(r"（\s*(.+?)\s*[～~]\s*(.+?)\s*）")


def _read_rdp_update_text() -> str | None:
    """rdp_update.toml の中身（文字列）を返す。Volume 優先・失敗時ローカルfallback。

    ``pptx_builder.load_template_bytes`` と同じ WorkspaceClient パターンで Volume から
    ``[rdp] update_toml_path`` を取得し、失敗した場合は ``local_fallback`` をローカルで読む。
    どちらも取得できない場合は None。
    """
    config = _load_rdp_config()
    path = config.get("update_toml_path", "")
    local_fallback = config.get("local_fallback", "")

    if path:
        try:
            from databricks.sdk import WorkspaceClient  # noqa: PLC0415

            w = WorkspaceClient()
            resp = w.files.download(path)
            return resp.contents.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Volume からの rdp_update.toml 取得に失敗（%s）。ローカルfallbackを使用: %s",
                path,
                e,
            )

    if local_fallback:
        try:
            with open(local_fallback, encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            logger.warning("rdp_update.toml のローカル読込に失敗（%s）: %s", local_fallback, e)
    return None


@st.cache_data(ttl=300, show_spinner=False)
def load_shipment_period() -> str | None:
    """出荷実績の対象期間文字列（例 ``2026年06月～2026年06月``）を返す。取得不可時は None。

    データ更新ジョブが Volume へ書き出す ``rdp_update.toml``
    （``プラズマドライ計 = 期間①（YYYY年MM月 ～ YYYY年MM月）``）から、プラズマ（先頭行）の
    期間を取り出す。プラズマ・おい免・ムテキッズは同一日時想定のためプラズマのみ使用する
    （issue 202607231113）。短い TTL でキャッシュし、更新後に追随する。
    """
    text = _read_rdp_update_text()
    if not text:
        return None
    m = _PERIOD_RE.search(text)
    if not m:
        logger.warning("rdp_update.toml から期間を解析できませんでした")
        return None
    return f"{m.group(1).strip()}～{m.group(2).strip()}"


def _table_and_spark(key: str = "table"):
    """Return (table_name, spark_session) for Databricks queries.

    *key* selects which config entry under ``[databricks]`` to read: ``table``
    (店舗×推進園 結合テーブル、既定) or ``store_table``（小売店マスタ）。
    """
    from databricks.connect import DatabricksSession  # noqa: PLC0415

    config = _load_databricks_config()
    # TODO: config/databricks_config.toml の table / store_table キーに実際のテーブル名を設定してください
    table_name = config.get(key, "catalog.schema.table_name")
    spark = DatabricksSession.builder.serverless(True).getOrCreate()
    return table_name, spark


def _rename_to_app_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename table columns to app column names using column_mapping.toml."""
    mapping = _load_column_mapping()
    # mapping: {app_name: col_name} -> rename col_name to app_name
    rename = {col_name: app_name for app_name, col_name in mapping.items() if col_name in df.columns}
    return df.rename(columns=rename) if rename else df


@st.cache_data(show_spinner="企業名称を取得中...")
def load_company_names() -> list[str]:
    """
    Lightweight startup query: distinct 企業名称 only.

    企業名称の候補は小売店マスタ（``store_table``）から取得する（issue 202607221245）。
    店舗×推進園テーブルは圏内推進園のある企業しか含まないのに対し、小売店マスタは
    企業の全店舗を持つため、候補としてはこちらが正しい。全件はロードせず、DISTINCT の
    企業名称（数百件）のみを取得する。
    """
    mapping = _load_column_mapping()
    company_col = mapping.get("企業名称", "企業名称")

    table_name, spark = _table_and_spark(key="store_table")
    rows = spark.table(table_name).select(company_col).distinct().toPandas()
    return sorted(rows[company_col].dropna().astype(str).tolist())


@st.cache_data(ttl=300, show_spinner=False)
def load_table_last_updated_ts() -> pd.Timestamp | None:
    """
    Return the JST ``pd.Timestamp`` of the table's latest data update, or None.

    Reads DESCRIBE HISTORY and keeps only data-modifying operations
    (WRITE/MERGE/UPDATE/DELETE/...), so maintenance operations such as
    OPTIMIZE/VACUUM do not count as "data updates".  Cached with a short TTL so
    callers refresh after a Databricks job updates the table.  This is the single
    source of the "data last-updated" moment; both the header string
    (``load_table_last_updated``) and the pptx date captions derive from it.
    """
    from pyspark.sql import functions as F  # noqa: PLC0415

    data_ops = [
        "WRITE", "MERGE", "UPDATE", "DELETE", "TRUNCATE", "COPY INTO",
        "STREAMING UPDATE", "CREATE TABLE AS SELECT",
        "REPLACE TABLE AS SELECT", "CREATE OR REPLACE TABLE AS SELECT",
    ]

    table_name, spark = _table_and_spark()
    pdf = (
        spark.sql(f"DESCRIBE HISTORY {table_name}")
        .where(F.col("operation").isin(data_ops))
        .agg(F.max("timestamp").alias("ts"))
        .toPandas()
    )
    if pdf.empty or pd.isna(pdf["ts"].iloc[0]):
        return None

    ts = pd.Timestamp(pdf["ts"].iloc[0])
    if ts.tzinfo is None:  # serverless セッションは UTC 想定
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("Asia/Tokyo")


def load_table_last_updated() -> str | None:
    """Return the JST datetime string of the table's latest data update, or None.

    ``load_table_last_updated_ts()`` を ``"%Y-%m-%d %H:%M"`` に整形した表示用文字列。
    """
    ts = load_table_last_updated_ts()
    return ts.strftime("%Y-%m-%d %H:%M") if ts is not None else None


@st.cache_data(show_spinner="データを取得中...")
def load_filtered(company: str, fetch_radius_km: float) -> pd.DataFrame:
    """
    Fetch rows for one *company* within *fetch_radius_km* from Databricks.

    Spark-side filter: 企業名称 == company AND 距離km <= fetch_radius_km.
    Cached by (company, fetch_radius_km) so repeating the same request hits
    the cache and changing either argument triggers a fresh query.
    """
    from pyspark.sql import functions as F  # noqa: PLC0415

    mapping = _load_column_mapping()
    company_col = mapping.get("企業名称", "企業名称")
    distance_col = mapping.get("距離km", "距離km")

    table_name, spark = _table_and_spark()
    sdf = (
        spark.table(table_name)
        .where(F.col(company_col) == company)
        .where(F.col(distance_col) <= float(fetch_radius_km))
    )
    return _rename_to_app_columns(sdf.toPandas())


@st.cache_data(show_spinner="小売店を取得中...")
def load_stores(company: str) -> pd.DataFrame:
    """Fetch the store master rows for one *company* from ``store_table``.

    小売店マスタ（企業G名称/企業名称/店舗名称/店舗コード/店舗_都道府県 ＋ 出荷実績9列 の
    DISTINCT）を企業で絞って取得する。``load_filtered`` が距離で削るのと異なり距離条件を
    課さないため、圏内推進園0件の店舗も残る。これを選択肢・下部集計表の土台に使う
    （issue 202607221128）。出荷実績は店舗別 推進園数テーブルへ載せる（issue 202607231113）。
    Cached by *company*.
    """
    from pyspark.sql import functions as F  # noqa: PLC0415

    mapping = _load_column_mapping()
    company_col = mapping.get("企業名称", "企業名称")
    select_cols = [
        mapping.get(c, c)
        for c in (
            "企業G名称", "企業名称", "店舗名称", "店舗コード", "店舗_都道府県",
            *SALES_COLUMNS,
        )
    ]

    table_name, spark = _table_and_spark(key="store_table")
    sdf = (
        spark.table(table_name)
        .where(F.col(company_col) == company)
        .select(*select_cols)
        .distinct()
    )
    return _rename_to_app_columns(sdf.toPandas())


@st.cache_data(show_spinner="企業Gを取得中...")
def load_company_group_names() -> list[str]:
    """Return the distinct 企業G名称 list from ``store_table`` (本部担当用ページ用).

    ``load_company_names`` と同形の軽量クエリ。本部担当用ページの企業G選択肢に使う
    （issue 202607231301）。全件はロードせず DISTINCT の企業G名称のみを取得する。
    """
    mapping = _load_column_mapping()
    group_col = mapping.get("企業G名称", "企業G名称")

    table_name, spark = _table_and_spark(key="store_table")
    rows = spark.table(table_name).select(group_col).distinct().toPandas()
    return sorted(rows[group_col].dropna().astype(str).tolist())


@st.cache_data(show_spinner="小売店を取得中...")
def load_stores_by_group(group: str) -> pd.DataFrame:
    """Fetch the store master rows for one 企業G名称 *group* from ``store_table``.

    ``load_stores`` の企業→企業G版（本部担当用ページ用, issue 202607231301）。
    select列は ``load_stores`` と同じ（企業G名称/企業名称/店舗名称/店舗コード/店舗_都道府県 ＋
    出荷実績9列 の DISTINCT）。企業Gは複数企業を跨ぐため、店舗別 推進園数表で企業名称を出せる。
    Cached by *group*.
    """
    from pyspark.sql import functions as F  # noqa: PLC0415

    mapping = _load_column_mapping()
    group_col = mapping.get("企業G名称", "企業G名称")
    select_cols = [
        mapping.get(c, c)
        for c in (
            "企業G名称", "企業名称", "店舗名称", "店舗コード", "店舗_都道府県",
            *SALES_COLUMNS,
        )
    ]

    table_name, spark = _table_and_spark(key="store_table")
    sdf = (
        spark.table(table_name)
        .where(F.col(group_col) == group)
        .select(*select_cols)
        .distinct()
    )
    return _rename_to_app_columns(sdf.toPandas())


@st.cache_data(show_spinner="データを取得中...")
def load_filtered_by_group(group: str, fetch_radius_km: float) -> pd.DataFrame:
    """Fetch rows for one 企業G名称 *group* within *fetch_radius_km* from Databricks.

    ``load_filtered`` の企業→企業G版（本部担当用ページ用, issue 202607231301）。
    Spark-side filter: 企業G名称 == group AND 距離km <= fetch_radius_km.
    Cached by (group, fetch_radius_km).
    """
    from pyspark.sql import functions as F  # noqa: PLC0415

    mapping = _load_column_mapping()
    group_col = mapping.get("企業G名称", "企業G名称")
    distance_col = mapping.get("距離km", "距離km")

    table_name, spark = _table_and_spark()
    sdf = (
        spark.table(table_name)
        .where(F.col(group_col) == group)
        .where(F.col(distance_col) <= float(fetch_radius_km))
    )
    return _rename_to_app_columns(sdf.toPandas())


def store_names(df: pd.DataFrame) -> list[str]:
    """Return unique 店舗名称 values sorted ascending."""
    return sorted(df["店舗名称"].unique().tolist())


def company_names(df: pd.DataFrame) -> list[str]:
    """Return unique 企業名称 values sorted ascending."""
    return sorted(df["企業名称"].unique().tolist())


def stores_for_company(df: pd.DataFrame, company: str) -> list[str]:
    """Return unique 店舗名称 for *company*, sorted ascending (cascade select)."""
    return sorted(df[df["企業名称"] == company]["店舗名称"].unique().tolist())


def prefectures_for_company(df: pd.DataFrame, company: str) -> list[str]:
    """Return unique 店舗_都道府県 for *company*, sorted ascending (image-DL filter)."""
    return sorted(df[df["企業名称"] == company]["店舗_都道府県"].unique().tolist())


def stores_for_company_prefectures(
    df: pd.DataFrame, company: str, prefectures: list[str]
) -> list[str]:
    """Return 店舗名称 for *company* whose 店舗_都道府県 is in *prefectures*, sorted."""
    sub = df[(df["企業名称"] == company) & (df["店舗_都道府県"].isin(prefectures))]
    return sorted(sub["店舗名称"].unique().tolist())


def store_count_for_company_prefectures(
    df: pd.DataFrame, company: str, prefectures: list[str]
) -> int:
    """Return the number of unique stores for *company* in *prefectures*."""
    sub = df[(df["企業名称"] == company) & (df["店舗_都道府県"].isin(prefectures))]
    return sub["店舗名称"].nunique()


def filter_facilities(
    df: pd.DataFrame, store_name: str, radius_km: float
) -> pd.DataFrame:
    """
    Return facilities for *store_name* within *radius_km*, sorted by 距離km.
    Adds a 1-based 連番 column.  No deduplication (SPEC §4.3).
    """
    filtered = (
        df[(df["店舗名称"] == store_name) & (df["距離km"] <= radius_km)]
        .sort_values("距離km")
        .reset_index(drop=True)
    )
    filtered["連番"] = filtered.index + 1
    return filtered


def filter_company(
    df: pd.DataFrame,
    company: str,
    radius_km: float,
    prefectures: list[str] | None = None,
) -> pd.DataFrame:
    """
    Return all facilities for *company* within *radius_km*, for single-file export.

    Filters by 企業名称 and 距離km <= radius, sorted by 店舗名称 then 距離km.
    If *prefectures* is provided, also filters by 店舗_都道府県.
    No 連番 column (rows span multiple stores).  No deduplication (SPEC §4.3).
    """
    mask = (df["企業名称"] == company) & (df["距離km"] <= radius_km)
    if prefectures:
        mask &= df["店舗_都道府県"].isin(prefectures)
    return (
        df[mask]
        .sort_values(["店舗名称", "距離km"])
        .reset_index(drop=True)
    )


def store_nursery_counts(
    stores_df: pd.DataFrame,
    nursery_df: pd.DataFrame,
    include_company: bool = False,
) -> pd.DataFrame:
    """小売店マスタに圏内推進園数を left join した集計表を返す。

    *stores_df* は ``load_stores`` の小売店マスタ（企業内の全店舗）、*nursery_df* は
    ``load_filtered`` の店舗×推進園（企業名称一致 & 距離km<=取得半径）。

    推進園数は *nursery_df* から ``COUNT(DISTINCT 推進園名称)`` を店舗キーで集計し、
    小売店マスタへ **left join** して埋める。圏内0件の店舗も残り、推進園数は 0 になる
    （issue 202607221128: 圏内0件の店舗が集計表から消える問題の解消）。
    列は 店舗名称 / 店舗コード / 店舗_都道府県 / 推進園数 ＋ 出荷実績9列（存在する分のみ,
    issue 202607231113）。出荷実績は店舗単位で一意のため小売店マスタから持ち込む。

    *include_company* が True のとき先頭に 企業名称 列を加える（本部担当用ページ, issue
    202607231301）。企業Gは複数企業を跨ぐため、店舗名称の衝突を避けるべく企業名称も
    集計・結合キーに含める。
    """
    lead_cols = ["企業名称"] if include_company else []
    cols = [*lead_cols, "店舗名称", "店舗コード", "店舗_都道府県"]
    # 実績列は小売店マスタに存在する分のみ載せる（サンプルデータ等で欠けても壊れない）。
    sales_cols = [c for c in SALES_COLUMNS if c in stores_df.columns]
    if stores_df.empty:
        return pd.DataFrame(columns=[*cols, "推進園数", *sales_cols])

    base = stores_df[[*cols, *sales_cols]].drop_duplicates(subset=cols)
    if nursery_df.empty:
        counts = pd.DataFrame(columns=[*cols, "推進園数"])
    else:
        counts = (
            nursery_df.groupby(cols, as_index=False)["推進園名称"]
            .nunique()
            .rename(columns={"推進園名称": "推進園数"})
        )
    merged = base.merge(counts, on=cols, how="left")
    merged["推進園数"] = merged["推進園数"].fillna(0).astype(int)
    # 列順: （企業名称）→ 店舗キー → 推進園数 → 実績9列。
    merged = merged[[*cols, "推進園数", *sales_cols]]
    sort_cols = [*lead_cols, "店舗名称", "店舗コード"]
    return merged.sort_values(sort_cols).reset_index(drop=True)


# Web Mercator ground resolution at zoom 0, equator (meters/pixel for 256px tiles).
_MPP_ZOOM0 = 156543.03392


def zoom_for_radius(
    radius_km: float,
    lat: float = 35.0,
    viewport_px: int = 600,
    fraction: float = 0.95,
    max_zoom: int = 19,
) -> int:
    """
    Return the largest zoom at which the radius circle fits in the viewport.

    The previous fixed step table (SPEC §6.1.2) zoomed in too far, pushing the
    radius circle off-screen.  Instead, choose zoom so the circle diameter
    (2 * radius_km * 1000 m) occupies about *fraction* of *viewport_px*:

        mpp(z) = 156543.03392 * cos(lat) / 2**z   (meters per pixel)
        want   diameter_m / mpp(z) <= fraction * viewport_px

    *fraction* is the share of the viewport the circle is allowed to fill; using
    ``floor`` above keeps the actual share in ``(fraction/2, fraction]`` so the
    circle always fits.  It is set to 0.95 (rather than a lower value) so small
    radii such as 1 km and 2 km zoom in one extra step while still leaving a
    small margin; larger radii like 3 km stay put because bumping them would push
    the circle off-screen.

    Clamped to ``[0, max_zoom]``.  *max_zoom* is the selected basemap's maximum
    zoom (e.g. GSI styles cap below OSM's 19), so tiles are never requested at a
    zoom the tile source does not serve.
    """
    diameter_m = 2.0 * radius_km * 1000.0
    target_mpp = (fraction * viewport_px) and (diameter_m / (fraction * viewport_px))
    if target_mpp <= 0:
        return max_zoom
    z = math.floor(math.log2(_MPP_ZOOM0 * math.cos(math.radians(lat)) / target_mpp))
    return max(0, min(max_zoom, int(z)))
