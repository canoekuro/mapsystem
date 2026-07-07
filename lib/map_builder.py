"""
Map generation helper for mapsystem.

Functions
---------
build_map(store_row, facilities_df, radius_km) -- build a folium.Map for a store
"""

import folium
from folium.plugins import BeautifyIcon

from lib.data import zoom_for_radius

# Color mapping by 推進園区分 (SPEC §6.1.2)
_FACILITY_COLORS: dict[str, str] = {
    "認可保育所": "#22C55E",
    "認定こども園": "#F59E0B",
    "幼稚園": "#EF4444",
}
_FALLBACK_COLOR = "#6B7280"


def build_map(store_row, facilities_df, radius_km: float) -> folium.Map:
    """
    Build a folium.Map centred on *store_row* showing a radius circle,
    the store marker, and numbered facility markers.

    Parameters
    ----------
    store_row : pandas.Series
        One row from master.csv.  Must contain 店舗lat, 店舗lon, 店舗名称.
    facilities_df : pandas.DataFrame
        Output of lib.data.filter_facilities (distance-sorted, with 連番 column).
        Must contain 推進園lat, 推進園lon, 推進園名称, 推進園区分, 距離km, 連番.
    radius_km : float
        Search radius in km.

    Returns
    -------
    folium.Map
    """
    lat = store_row["店舗lat"]
    lon = store_row["店舗lon"]
    store_name = store_row["店舗名称"]

    # --- 1. Map base ---
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_for_radius(radius_km, lat, viewport_px=560),
        tiles="OpenStreetMap",
        width=700,
        height=560,
    )

    # --- 2. Radius circle (SPEC §6.1.2) ---
    folium.Circle(
        location=[lat, lon],
        radius=radius_km * 1000,
        color="#7C3AED",
        weight=2,
        dash_array="8,8",
        fill=True,
        fill_color="#7C3AED",
        fill_opacity=0.08,
    ).add_to(m)

    # --- 3. Store marker (SPEC §6.1.2) ---
    folium.Marker(
        location=[lat, lon],
        icon=folium.Icon(color="black", icon="shopping-cart", prefix="fa"),
        tooltip=store_name,
    ).add_to(m)

    # --- 4. Facility markers (SPEC §6.1.2) ---
    for _, row in facilities_df.iterrows():
        category = row["推進園区分"]
        bg_color = _FACILITY_COLORS.get(category, _FALLBACK_COLOR)
        number = int(row["連番"])
        distance = row["距離km"]
        facility_name = row["推進園名称"]

        icon = BeautifyIcon(
            icon_shape="circle",
            number=number,
            border_color=bg_color,
            background_color=bg_color,
            text_color="#FFFFFF",
        )
        folium.Marker(
            location=[row["推進園lat"], row["推進園lon"]],
            tooltip=f"{number}. {facility_name}（{distance:.2f}km）",
            icon=icon,
        ).add_to(m)

    return m
