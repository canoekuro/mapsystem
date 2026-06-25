"""
Data access helpers — reads master data from Databricks Unity Catalog.

Functions
---------
load_master()                          -- cached table loader (applies column mapping)
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


@st.cache_data
def load_master() -> pd.DataFrame:
    """Load master table from Databricks Unity Catalog and apply column name mapping."""
    from databricks.connect import DatabricksSession  # noqa: PLC0415

    config = _load_databricks_config()
    # TODO: config/databricks_config.toml の table キーに実際のテーブル名を設定してください
    table_name = config.get("table", "catalog.schema.table_name")

    spark = DatabricksSession.builder.getOrCreate()
    df = spark.table(table_name).toPandas()

    mapping = _load_column_mapping()
    # mapping: {app_name: col_name} -> rename col_name to app_name
    rename = {col_name: app_name for app_name, col_name in mapping.items() if col_name in df.columns}
    if rename:
        df = df.rename(columns=rename)
    return df


def store_names(df: pd.DataFrame) -> list[str]:
    """Return unique 小売店名称 values sorted ascending."""
    return sorted(df["小売店名称"].unique().tolist())


def company_names(df: pd.DataFrame) -> list[str]:
    """Return unique 企業名称 values sorted ascending."""
    return sorted(df["企業名称"].unique().tolist())


def stores_for_company(df: pd.DataFrame, company: str) -> list[str]:
    """Return unique 小売店名称 for *company*, sorted ascending (cascade select)."""
    return sorted(df[df["企業名称"] == company]["小売店名称"].unique().tolist())


def prefectures_for_company(df: pd.DataFrame, company: str) -> list[str]:
    """Return unique 都道府県 for *company*, sorted ascending (image-DL filter)."""
    return sorted(df[df["企業名称"] == company]["都道府県"].unique().tolist())


def stores_for_company_prefectures(
    df: pd.DataFrame, company: str, prefectures: list[str]
) -> list[str]:
    """Return 小売店名称 for *company* whose 都道府県 is in *prefectures*, sorted."""
    sub = df[(df["企業名称"] == company) & (df["都道府県"].isin(prefectures))]
    return sorted(sub["小売店名称"].unique().tolist())


def store_count_for_company_prefectures(
    df: pd.DataFrame, company: str, prefectures: list[str]
) -> int:
    """Return the number of unique stores for *company* in *prefectures*."""
    sub = df[(df["企業名称"] == company) & (df["都道府県"].isin(prefectures))]
    return sub["小売店名称"].nunique()


def filter_facilities(
    df: pd.DataFrame, store_name: str, radius_km: float
) -> pd.DataFrame:
    """
    Return facilities for *store_name* within *radius_km*, sorted by 距離.
    Adds a 1-based 連番 column.  No deduplication (SPEC §4.3).
    """
    filtered = (
        df[(df["小売店名称"] == store_name) & (df["距離"] <= radius_km)]
        .sort_values("距離")
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

    Filters by 企業名称 and 距離 <= radius, sorted by 小売店名称 then 距離.
    If *prefectures* is provided, also filters by 都道府県.
    No 連番 column (rows span multiple stores).  No deduplication (SPEC §4.3).
    """
    mask = (df["企業名称"] == company) & (df["距離"] <= radius_km)
    if prefectures:
        mask &= df["都道府県"].isin(prefectures)
    return (
        df[mask]
        .sort_values(["小売店名称", "距離"])
        .reset_index(drop=True)
    )


# Web Mercator ground resolution at zoom 0, equator (meters/pixel for 256px tiles).
_MPP_ZOOM0 = 156543.03392


def zoom_for_radius(
    radius_km: float, lat: float = 35.0, viewport_px: int = 600, fraction: float = 0.8
) -> int:
    """
    Return the largest zoom at which the radius circle fits in the viewport.

    The previous fixed step table (SPEC §6.1.2) zoomed in too far, pushing the
    radius circle off-screen.  Instead, choose zoom so the circle diameter
    (2 * radius_km * 1000 m) occupies about *fraction* of *viewport_px*:

        mpp(z) = 156543.03392 * cos(lat) / 2**z   (meters per pixel)
        want   diameter_m / mpp(z) <= fraction * viewport_px

    Clamped to the OSM tile range [0, 19].
    """
    diameter_m = 2.0 * radius_km * 1000.0
    target_mpp = (fraction * viewport_px) and (diameter_m / (fraction * viewport_px))
    if target_mpp <= 0:
        return 19
    z = math.floor(math.log2(_MPP_ZOOM0 * math.cos(math.radians(lat)) / target_mpp))
    return max(0, min(19, int(z)))
