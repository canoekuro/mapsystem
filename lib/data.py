"""
Data access helpers for master.csv.

Functions
---------
load_master()         -- cached CSV loader
store_names(df)       -- unique store names (sorted)
company_names(df)     -- unique company names (sorted)
filter_facilities()   -- filter by store + radius, add 連番
filter_company()      -- filter by company + radius (for single-file export)
zoom_for_radius()     -- zoom level that keeps the radius circle in view
"""

import math

import pandas as pd
import streamlit as st


@st.cache_data
def load_master() -> pd.DataFrame:
    """Load data/master.csv.  Exceptions propagate to the caller (SPEC §11)."""
    return pd.read_csv("data/master.csv")


def store_names(df: pd.DataFrame) -> list[str]:
    """Return unique 小売店名称 values sorted ascending."""
    return sorted(df["小売店名称"].unique().tolist())


def company_names(df: pd.DataFrame) -> list[str]:
    """Return unique 企業名称 values sorted ascending."""
    return sorted(df["企業名称"].unique().tolist())


def stores_for_company(df: pd.DataFrame, company: str) -> list[str]:
    """Return unique 小売店名称 for *company*, sorted ascending (cascade select)."""
    return sorted(df[df["企業名称"] == company]["小売店名称"].unique().tolist())


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


def filter_company(df: pd.DataFrame, company: str, radius_km: float) -> pd.DataFrame:
    """
    Return all facilities for *company* within *radius_km*, for single-file export.

    Filters by 企業名称 and 距離 <= radius, sorted by 小売店名称 then 距離.
    No 連番 column (rows span multiple stores).  No deduplication (SPEC §4.3).
    """
    return (
        df[(df["企業名称"] == company) & (df["距離"] <= radius_km)]
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
