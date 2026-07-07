# 計画: 地図の背景（OSM/GSI/CARTO）を設定ページで選択可能にする

- **日時:** 2026-07-07 13:32
- **テーマ:** ベースマップ（背景タイル）の切替を設定ページから。既定値は toml で指定。

## 1. 背景・目的

地図タイルは OSM 標準に固定だった。設定ページから **OSM / 国土地理院(GSI) / CARTO(OSMベース)**
とそれぞれのスタイルを選べるようにし、**既定値を `config/theme.toml` で指定** する。
ラスターXYZ方式のままなので folium・PNG 双方が URL＋帰属表示の差し替えで対応できる。

## 2. 変更内容

### 新規 `lib/basemaps.py`
`BASEMAPS`（id -> `{label, provider, url, attribution, max_zoom}`）と参照ヘルパー
（`get_basemap`/`is_valid`/`providers`/`basemaps_for_provider`）。純データ。
- OSM: 標準 / Humanitarian、GSI: 標準 / 淡色 / 航空写真 / 白地図、
  CARTO: Positron / Voyager / Dark Matter。

### 設定への相乗り
- `config/theme.toml` に `[map] basemap`。
- `lib/colors.py`: `_DEFAULTS["basemap"]`、`_load_from_file` で `[map]` も読む、`_merge` で basemap
  検証、`basemap_id()` アクセサ、`theme_toml_text`/`save_theme` に `[map]` 出力。

### 描画側
- `lib/data.py::zoom_for_radius(..., max_zoom=19)` 追加（クランプ上限を可変化）。
- `lib/map_builder.py`: folium を `tiles=bm.url, attr=bm.attribution, max_zoom=bm.max_zoom`、
  `zoom_start` も basemap max_zoom を渡す。
- `lib/static_map.py`: `tile_url = OSM_TILE_URL(env) or bm.url`、zoom を basemap max_zoom でクランプ、
  `_fetch_tile(z,x,y,url_template)`（キャッシュキーに url を含め basemap 混在を防止）、
  PNG 右下に帰属表示を焼き込む（`_draw_attribution`）。

### 設定ページ
- `views/config_page.py`: 「地図の背景」節。提供元→スタイルの2段 `st.selectbox`、`values["basemap"]`
  に反映、保存/既定に戻す/TOML DL/プレビュー(caption)に相乗り。

### ドキュメント
- `SPEC.md` §6.1.2/§6.4/§8.3/§9、`docs/history/`、`CHANGELOG.md`。
- PR #11 マージ済みのため最新 main からブランチを作り直し新規 PR。

## 3. 検証方法
- catalog 解決・未知idフォールバック、`save_theme({"basemap":...})` 往復。
- タイル取得を url ごとにモックし OSM/GSI で取得URL一致・PNG右下に帰属表示・PNG差分を確認。
- folium render HTML に basemap url が含まれる、`gsi_blank`(z14) でズームがクランプ、`_fetch_tile`
  署名に url_template。
- 設定ページ（streamlit スタブ）で 提供元→スタイル→basemap id、既定に戻すで osm_standard。

## 4. 留意
- Databricks Apps の送信許可に `cyberjapandata.gsi.go.jp` / `tile.openstreetmap.fr` /
  `basemaps.cartocdn.com` が必要。帰属表示必須（対応済み）。無料タイルの一括DLはレート制限注意。
