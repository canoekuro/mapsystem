"""
Data access helpers — reads master data from Databricks Unity Catalog.

Functions
---------
load_company_names()                   -- cached lightweight distinct 企業名称 loader
load_filtered()                        -- fetch one company within fetch radius (Spark-side filter)
load_stores()                          -- fetch the store master for one company (no radius filter)
store_names(df)                        -- unique store names (sorted)
company_names(df)                      -- unique company names (sorted)
filter_facilities()                    -- filter by store + radius, add 連番
filter_company()                       -- filter by company + radius (for single-file export)
store_count_for_company_prefectures()  -- store count for company + prefecture selection
zoom_for_radius()                      -- zoom level that keeps the radius circle in view
"""

import math
import tomllib

import pandas as pd
import streamlit as st

_COLUMN_MAPPING_PATH = "config/column_mapping.toml"
_DATABRICKS_CONFIG_PATH = "config/databricks_config.toml"


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

    Avoids loading the full table — only the (few hundred) distinct company
    names are pulled, so the app starts fast and queries on demand.
    """
    mapping = _load_column_mapping()
    company_col = mapping.get("企業名称", "企業名称")

    table_name, spark = _table_and_spark()
    rows = spark.table(table_name).select(company_col).distinct().toPandas()
    return sorted(rows[company_col].dropna().astype(str).tolist())


@st.cache_data(ttl=300, show_spinner=False)
def load_table_last_updated() -> str | None:
    """
    Return the JST datetime string of the table's latest data update, or None.

    Reads DESCRIBE HISTORY and keeps only data-modifying operations
    (WRITE/MERGE/UPDATE/DELETE/...), so maintenance operations such as
    OPTIMIZE/VACUUM do not count as "data updates".  Cached with a short TTL so
    the display refreshes after a Databricks job updates the table.
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
    return ts.tz_convert("Asia/Tokyo").strftime("%Y-%m-%d %H:%M")


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

    小売店マスタ（企業名称/店舗名称/店舗コード/店舗_都道府県 の DISTINCT）を企業で
    絞って取得する。``load_filtered`` が距離で削るのと異なり距離条件を課さないため、
    圏内推進園0件の店舗も残る。これを選択肢・下部集計表の土台に使う（issue 202607221128）。
    Cached by *company*.
    """
    from pyspark.sql import functions as F  # noqa: PLC0415

    mapping = _load_column_mapping()
    company_col = mapping.get("企業名称", "企業名称")
    select_cols = [
        mapping.get(c, c)
        for c in ("企業名称", "店舗名称", "店舗コード", "店舗_都道府県")
    ]

    table_name, spark = _table_and_spark(key="store_table")
    sdf = (
        spark.table(table_name)
        .where(F.col(company_col) == company)
        .select(*select_cols)
        .distinct()
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
    stores_df: pd.DataFrame, nursery_df: pd.DataFrame
) -> pd.DataFrame:
    """小売店マスタに圏内推進園数を left join した集計表を返す。

    *stores_df* は ``load_stores`` の小売店マスタ（企業内の全店舗）、*nursery_df* は
    ``load_filtered`` の店舗×推進園（企業名称一致 & 距離km<=取得半径）。

    推進園数は *nursery_df* から ``COUNT(DISTINCT 推進園名称)`` を店舗キーで集計し、
    小売店マスタへ **left join** して埋める。圏内0件の店舗も残り、推進園数は 0 になる
    （issue 202607221128: 圏内0件の店舗が集計表から消える問題の解消）。
    列は 店舗名称 / 店舗コード / 店舗_都道府県 / 推進園数。
    """
    cols = ["店舗名称", "店舗コード", "店舗_都道府県"]
    if stores_df.empty:
        return pd.DataFrame(columns=[*cols, "推進園数"])

    base = stores_df[cols].drop_duplicates()
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
    return merged.sort_values(["店舗名称", "店舗コード"]).reset_index(drop=True)


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
