# OSMFJ タイルをベースマップに追加（結果）

- 日付時刻: 2026-07-10 00:34:44
- テーマ: 地図スタイルへ OSMFJ（OpenStreetMap Foundation Japan）タイルを追加
- ブランチ: `claude/osm-map-style-qz7bxw`
- 対の計画: [計画](20260710-003444-osmfj-basemap-plan.md)

## 変更内容

1. `lib/basemaps.py`
   - `BASEMAPS` に `osmfj_japan` を追加（`osm_hot` の直後）。
     - `label`: "日本語スタイル"
     - `provider`: `PROVIDER_OSM`（既存 "OpenStreetMap" グループ）
     - `url`: `https://tile.openstreetmap.jp/{z}/{x}/{y}.png`
     - `attribution`: `© OpenStreetMap contributors, Tiles: OSMFJ`
     - `max_zoom`: 18
2. `config/theme.toml`
   - コメントの OSM id 一覧に `osmfj_japan` を追記。

## 検証結果

`lib.basemaps` を import して確認（すべて期待通り）:

- `is_valid("osmfj_japan")` → `True`
- `basemaps_for_provider("OpenStreetMap")` の id →
  `['osm_standard', 'osm_hot', 'osmfj_japan']`
- `providers()` → `['OpenStreetMap', '国土地理院', 'CARTO']`（3件のまま、新グループなし）
- `get_basemap("osmfj_japan")` → label/provider/url/max_zoom すべて定義通り

## 未対応事項

- OSMFJ サーバーの利用規約・負荷方針の確認（運用判断）。高負荷・商用時は
  安定配信の他提供元（CARTO 等）も検討余地あり。
- タイル URL への実ネットワーク疎通確認は本作業では未実施（カタログ定義の追加のみ）。
