"""
Map generation helper for mapsystem.

Functions
---------
build_map(store_row, facilities_df, radius_km) -- build a folium.Map for a store
"""

import folium
from folium.plugins import BeautifyIcon

from lib.data import zoom_for_radius

# Color mapping by 施設区分 (SPEC §6.1.2)
_FACILITY_COLORS: dict[str, str] = {
    "保育園": "#22C55E",
    "幼稚園": "#EF4444",
    "こども園": "#F59E0B",
}
_FALLBACK_COLOR = "#6B7280"

_LEGEND_HTML = """
<div style="
    position: fixed;
    bottom: 30px;
    right: 10px;
    z-index: 1000;
    background-color: #FFFFFF;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1.8;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3);
">
    <span style="color:#22C55E; font-size:16px;">&#9679;</span> 保育園<br>
    <span style="color:#EF4444; font-size:16px;">&#9679;</span> 幼稚園<br>
    <span style="color:#F59E0B; font-size:16px;">&#9679;</span> こども園
</div>
"""


def build_map(store_row, facilities_df, radius_km: float) -> folium.Map:
    """
    Build a folium.Map centred on *store_row* showing a radius circle,
    the store marker, numbered facility markers, and a legend.

    Parameters
    ----------
    store_row : pandas.Series
        One row from master.csv.  Must contain 店舗緯度, 店舗経度, 小売店名称.
    facilities_df : pandas.DataFrame
        Output of lib.data.filter_facilities (distance-sorted, with 連番 column).
        Must contain 施設緯度, 施設経度, 施設名称, 施設区分, 距離, 連番.
    radius_km : float
        Search radius in km.

    Returns
    -------
    folium.Map
    """
    lat = store_row["店舗緯度"]
    lon = store_row["店舗経度"]
    store_name = store_row["小売店名称"]

    # --- 1. Map base ---
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_for_radius(radius_km),
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
        category = row["施設区分"]
        bg_color = _FACILITY_COLORS.get(category, _FALLBACK_COLOR)
        number = int(row["連番"])
        distance = row["距離"]
        facility_name = row["施設名称"]

        icon = BeautifyIcon(
            icon_shape="circle",
            number=number,
            border_color=bg_color,
            background_color=bg_color,
            text_color="#FFFFFF",
        )
        folium.Marker(
            location=[row["施設緯度"], row["施設経度"]],
            tooltip=f"{number}. {facility_name}（{distance}km）",
            icon=icon,
        ).add_to(m)

    # --- 5. Legend (SPEC §6.1.2) ---
    m.get_root().html.add_child(folium.Element(_LEGEND_HTML))

    return m
