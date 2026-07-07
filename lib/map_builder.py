"""
Map generation helper for mapsystem.

Functions
---------
build_map(store_row, facilities_df, radius_km) -- build a folium.Map for a store
"""

import folium
from folium.plugins import BeautifyIcon

from lib.colors import FACILITY_COLORS, facility_color
from lib.data import zoom_for_radius


def _legend_html() -> str:
    """推進園区分の凡例（地図左下に重ねる HTML 断片）。"""
    rows = "".join(
        '<div style="display:flex;align-items:center;margin:2px 0;">'
        f'<span style="width:12px;height:12px;border-radius:50%;'
        f'background:{color};display:inline-block;margin-right:6px;'
        'flex-shrink:0;"></span>'
        f'<span style="font-size:12px;color:#111827;">{category}</span>'
        "</div>"
        for category, color in FACILITY_COLORS.items()
    )
    return (
        '<div style="position:absolute;bottom:16px;left:16px;z-index:9999;'
        "background:rgba(255,255,255,0.92);padding:8px 10px;border-radius:6px;"
        'box-shadow:0 1px 4px rgba(0,0,0,0.3);border:1px solid #E5E7EB;">'
        '<div style="font-size:12px;font-weight:bold;color:#111827;'
        'margin-bottom:4px;">推進園区分</div>'
        f"{rows}</div>"
    )


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
        bg_color = facility_color(row["推進園区分"])
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

    # --- 5. Legend (推進園区分の色分け凡例, SPEC §6.1.2) ---
    m.get_root().html.add_child(folium.Element(_legend_html()))

    return m
