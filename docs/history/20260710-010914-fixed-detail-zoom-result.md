# 対話地図の情報粒度をズームから切り離して固定する（結果）

- 日付時刻: 2026-07-10 01:09:14
- テーマ: 対話地図の表示情報の粒度（詳細度）をズーム操作から切り離して固定
- ブランチ: `claude/osm-map-style-qz7bxw`
- 対の計画: [計画](20260710-010914-fixed-detail-zoom-plan.md)

## 変更内容

新テーマ設定キー `map_detail_zoom`（int, 既定 0）を追加。0=固定しない、1–19=その粒度で固定。

1. `lib/colors.py`
   - `_DEFAULTS["map_detail_zoom"] = 0`、`_DETAIL_ZOOM_MIN=0`/`_DETAIL_ZOOM_MAX=19` を追加。
   - `_load_from_file()` の `[map]` 読み込みキーに `map_detail_zoom` を追加。
   - `_merge()` に分岐を追加（int かつ bool 以外を 0–19 にクランプ）。
   - アクセサ `map_detail_zoom() -> int` を追加。Public API docstring も更新。
   - `theme_toml_text()` の `[map]` に `map_detail_zoom` 行（コメント併記）を追加。
2. `lib/map_builder.py`
   - `folium.Map(tiles=None, ...)` + 明示 `folium.TileLayer(...)` 方式へ変更。
   - `map_detail_zoom() > 0` のとき `fixed = min(detail, bm["max_zoom"])` を
     `max_native_zoom`/`min_native_zoom` に設定。0 のときは native zoom を付与しない。
3. `views/config_page.py`
   - `_MAP_DETAIL_ZOOM_KEY` を追加し、`_init_state`/`_reset_to_default`/`_collect_values` に配線。
   - 「情報の粒度（詳細度）」セクションに `number_input`（0–19, step 1）＋説明 caption を追加。
4. `config/theme.toml`
   - `[map]` に `map_detail_zoom = 0` とコメントを追記。
5. `SPEC.md`
   - §6.1.2 に `map_detail_zoom` 仕様を追記。あわせて背景選択肢に OSMFJ の記載を補正。

## 検証結果

`folium 0.20.0` で確認（すべて期待通り）:

- colors 単体: `map_detail_zoom` のクランプ（99→19 / -5→0 / bool→無視）と、
  `theme_toml_text()` に `map_detail_zoom = 0` 行が出ることを確認。既定は 0。
- `build_map()` の生成 HTML:
  - `detail=0`: `minNativeZoom` は出ず、`maxNativeZoom` は folium 既定で `maxZoom`
    と同値（＝従来と同じ挙動）。
  - `detail=15`: TileLayer の `maxNativeZoom`/`minNativeZoom` が両方 15。
  - `basemap=gsi_blank`（max_zoom 14）で `detail=18`: 両方 14 にクランプ。
- folium 0.20 は `max_native_zoom`/`min_native_zoom` を Leaflet の camelCase へ
  自動変換するため、計画に記したフォールバック（options 直接設定）は不要だった。

## 未対応事項

- ダウンロードPNG（`lib/static_map.py`）は今回対象外（半径からズーム自動計算のまま）。
- Streamlit を起動しての目視確認は本環境では未実施（folium 生成 HTML のオプション検証で代替）。
- 粒度を大きく下回るズームアウト時のタイル取得負荷は原理的トレードオフとして残る。
