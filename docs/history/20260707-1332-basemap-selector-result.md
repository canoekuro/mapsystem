# 結果: 地図の背景（OSM/GSI/CARTO）を設定ページで選択可能にする

- **日時:** 2026-07-07 13:32
- **対応 plan:** `docs/history/20260707-1332-basemap-selector-plan.md`

## 1. 変更内容

| ファイル | 変更 |
|---|---|
| `lib/basemaps.py`（新規） | ベースマップ catalog（OSM 標準/HOT、GSI 標準/淡色/写真/白地図、CARTO Positron/Voyager/Dark）＋参照ヘルパー |
| `config/theme.toml` | `[map] basemap`（既定 `osm_standard`）を追記 |
| `lib/colors.py` | `basemap` を既定/読込/検証/`basemap_id()`/`[map]` 出力に統合 |
| `lib/data.py` | `zoom_for_radius` に `max_zoom` 引数を追加（後方互換） |
| `lib/map_builder.py` | folium の `tiles`/`attr`/`max_zoom` を選択ベースマップから取得 |
| `lib/static_map.py` | タイルURLをベースマップから（`OSM_TILE_URL` env 優先）、zoom クランプ、`_fetch_tile` のキャッシュキーに url、PNG 右下に帰属表示を焼き込み |
| `views/config_page.py` | 「地図の背景」提供元→スタイルの2段セレクト、保存/既定/DL/プレビューに統合 |
| `SPEC.md` | §6.1.2/§6.4/§8.3/§9 を更新 |

## 2. 検証結果

- **catalog / 設定往復**: `providers()=[OpenStreetMap, 国土地理院, CARTO]`、未知idは `osm_standard` へ
  フォールバック、`theme_toml_text({"basemap":"gsi_pale"})` に `[map] basemap="gsi_pale"` が出力。
- **描画反映**（タイル取得を url 別モック）:
  - `osm_standard`/`gsi_pale` で取得URLが各ベースマップに一致。GSI 選択時の合成PNG右下に
    「出典: 国土地理院」を確認（PNG も OSM と差分あり）。
  - `map_builder.build_map` の render HTML に選択ベースマップの url を確認（attr は folium が
    非ASCIIを unicode エスケープするが `attr=` へ渡している）。
  - `zoom_for_radius(0.2, …, max_zoom=14)` が 14 以下にクランプ（既定 19 と差が出る）。
  - `_fetch_tile` の署名に `url_template`（キャッシュがベースマップ別に分離）。
- **設定ページ**（streamlit スタブ）: 提供元→スタイル選択で `basemap` が `gsi_pale` に、
  「既定に戻す」で `osm_standard` に戻ることを確認。

## 3. 未対応事項

- Databricks Apps 実機での目視・egress 許可（`cyberjapandata.gsi.go.jp` / `tile.openstreetmap.fr` /
  `basemaps.cartocdn.com`）は運用側で要確認。
- 無料タイルの一括DL（多数取得）はレート制限に注意（必要なら鍵付きプロバイダを別途検討）。
