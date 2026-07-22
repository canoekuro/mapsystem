"""
Map generation helper for mapsystem.

Functions
---------
build_map(store_row, facilities_df, radius_km) -- build a folium.Map for a store
"""

import folium
from folium.plugins import BeautifyIcon

from lib import icons
from lib.basemaps import get_basemap
from lib.colors import (
    basemap_id,
    circle_color,
    circle_fill_opacity,
    facility_color,
    facility_marker_size_for_radius,
    map_detail_zoom,
    map_height,
    map_width,
    store_marker_size,
)
from lib.data import zoom_for_radius

# 推進園マーカーの基準サイズ（px）。テーマの相対サイズ（％）をこの値へ掛けて実サイズを得る。
# 100％ でおおむね従来の見た目（BeautifyIcon 既定）を保つ。
_MARKER_BASE_PX = 30
# 推進園マーカーの番号の基準フォント（px、100％時）。
_FACILITY_NUMBER_BASE_PX = 11

# map_detail_zoom=0（固定しない）でも、情報粒度（タイル取得ズーム）が 15 以上に
# なるときは 14 で頭打ちにする（SPEC §6.1.2 追補）。
_DETAIL_ZOOM_CAP = 14


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

    # --- 1. Map base (テーマで背景・サイズを選択, SPEC §6.1.2) ---
    bm = get_basemap(basemap_id())
    m_width = map_width()
    m_height = map_height()
    # 固定画面: 拡大縮小・移動を一切無効化し、build_map の初期中心/ズームで固定表示する
    # （SPEC §6.1.2）。Leaflet の操作系オプションをすべて off にして誤操作でズレないようにし、
    # これにより「マップをリセット」ボタンを不要にする。
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom_for_radius(radius_km, lat, viewport_px=m_height, max_zoom=bm["max_zoom"]),
        tiles=None,
        max_zoom=bm["max_zoom"],
        width=m_width,
        height=m_height,
        zoom_control=False,      # ＋/− ズームボタンを非表示
        dragging=False,          # ドラッグでの移動を無効
        scrollWheelZoom=False,   # ホイールズームを無効
        doubleClickZoom=False,   # ダブルクリックズームを無効
        touchZoom=False,         # ピンチズームを無効
        boxZoom=False,           # 範囲選択ズームを無効
        keyboard=False,          # キーボード操作を無効
    )
    # 情報粒度（詳細度）の固定: detail_zoom > 0 のとき native zoom を固定し、
    # 地図をズームしてもタイル画像を拡大縮小するだけにして粒度を一定に保つ（SPEC §6.1.2）。
    # ベースマップが提供するズーム上限を超えないようクランプする。
    detail_zoom = map_detail_zoom()
    if detail_zoom > 0:
        fixed = min(detail_zoom, bm["max_zoom"])
        tile_opts: dict = {"max_native_zoom": fixed, "min_native_zoom": fixed}
    else:
        # 固定しない場合でも粒度は 14 で頭打ち（min は設定せず 14 以下はズームに追従）。
        tile_opts = {"max_native_zoom": min(_DETAIL_ZOOM_CAP, bm["max_zoom"])}
    folium.TileLayer(
        tiles=bm["url"],
        attr=bm["attribution"],
        max_zoom=bm["max_zoom"],
        **tile_opts,
    ).add_to(m)

    # --- 2. Radius circle (SPEC §6.1.2, テーマ調整可) ---
    circle_hex = circle_color()
    folium.Circle(
        location=[lat, lon],
        radius=radius_km * 1000,
        color=circle_hex,
        weight=2,
        dash_array="8,8",
        fill=True,
        fill_color=circle_hex,
        fill_opacity=circle_fill_opacity(),
    ).add_to(m)

    # --- 3. Store marker (SPEC §6.1.2) ---
    # 店舗アイコンは同梱画像 images/icon.png（ピン型）を使う。サイズはテーマの相対サイズ
    # （％）で調整し、ピン先端（tip）を店舗座標へ合わせる（icon_anchor）。
    store_w, store_h = icons.store_icon_size(store_marker_size())
    tip_rx, tip_ry = icons.store_icon_tip()
    folium.Marker(
        location=[lat, lon],
        icon=folium.CustomIcon(
            icon_image=icons.icon_path(),
            icon_size=[store_w, store_h],
            icon_anchor=[round(store_w * tip_rx), round(store_h * tip_ry)],
        ),
        tooltip=store_name,
    ).add_to(m)

    # --- 4. Facility markers (SPEC §6.1.2, サイズは地図半径ごとにテーマ調整可) ---
    fac_scale = facility_marker_size_for_radius(radius_km)
    fac_px = round(_MARKER_BASE_PX * fac_scale / 100)
    fac_number_px = round(_FACILITY_NUMBER_BASE_PX * fac_scale / 100)
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
            icon_size=[fac_px, fac_px],
            icon_anchor=[fac_px // 2, fac_px // 2],
            inner_icon_style=f"font-size:{fac_number_px}px;line-height:{fac_px}px;",
        )
        folium.Marker(
            location=[row["推進園lat"], row["推進園lon"]],
            tooltip=f"{number}. {facility_name}（{distance:.2f}km）",
            icon=icon,
        ).add_to(m)

    # 凡例は廃止（区分色分けをやめ単一色で描画するため, issue 202607161811）。

    return m
