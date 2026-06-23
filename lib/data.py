"""
Data access helpers for master.csv.

Functions
---------
load_master()         -- cached CSV loader
store_names(df)       -- unique store names (sorted)
company_names(df)     -- unique company names (sorted)
filter_facilities()   -- filter by store + radius, add 連番
zoom_for_radius()     -- folium zoom level from radius (km)
"""

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


def zoom_for_radius(radius_km: float) -> int:
    """Return folium zoom_start level for the given radius (SPEC §6.1.2)."""
    if radius_km <= 1:
        return 16
    elif radius_km <= 2:
        return 15
    elif radius_km <= 5:
        return 14
    elif radius_km <= 10:
        return 13
    else:
        return 12
