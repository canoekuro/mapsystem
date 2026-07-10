# 対話地図の情報粒度をズームから切り離して固定する（計画）

- 日付時刻: 2026-07-10 01:09:14
- テーマ: 対話地図の表示情報の粒度（詳細度）をズーム操作から切り離して固定
- ブランチ: `claude/osm-map-style-qz7bxw`

## 背景・目的

ラスタータイル（地理院タイル等）はズームレベルごとに描画内容が焼き込まれた画像で、
ズームすると表示される道路・地名・建物の粒度が自動的に変わる。ユーザーは対話地図で
この粒度を一定に保ちたい（挙動1: ズーム操作は残しつつ情報の細かさだけ固定）。
どのズーム相当の粒度に固定するかはテーマ設定ページで調整できるようにする。
今回の対象は対話地図（folium）のみ。ダウンロードPNG（`lib/static_map.py`）は対象外。

## 実現方法

Leaflet の `maxNativeZoom` / `minNativeZoom` を同一値に固定すると、タイルは常にその
1レベルだけを取得し、他ズームでは画像を拡大縮小するだけになる。結果、地図ズームを
変えても粒度が一定に保たれる（拡大時はぼやけ、縮小時は文字が小さくなるトレードオフは許容）。

## 変更内容

新テーマ設定キー `map_detail_zoom`（int, 既定 0）を導入。
- `0` = 固定しない（従来どおりズームに追従）。
- `1–19` = そのズーム相当の粒度で固定。
- 既定 0 によりオプトイン（既存の見え方は不変）。

1. `lib/colors.py`
   - `_DEFAULTS` に `map_detail_zoom: 0`、範囲定数 `_DETAIL_ZOOM_MIN/MAX`（0/19）を追加。
   - `_load_from_file()` の `[map]` 読み込みキーに追加。
   - `_merge()` に分岐（int かつ bool 以外を 0–19 にクランプ）。
   - アクセサ `map_detail_zoom()` を追加。
   - `theme_toml_text()` の `[map]` 出力に1行追加。
2. `lib/map_builder.py`
   - `folium.Map(tiles=None, ...)` + 明示 `folium.TileLayer(...)` 方式へ変更。
   - `map_detail_zoom() > 0` のとき `fixed = min(detail, bm["max_zoom"])` を
     `max_native_zoom`/`min_native_zoom` に設定。0 のときは付与しない。
3. `views/config_page.py`
   - `_MAP_DETAIL_ZOOM_KEY` を追加し、`_init_state`/`_reset_to_default`/`_collect_values` に配線。
   - 「情報の粒度（詳細度）」セクションに `number_input`（0–19）を追加。
4. `config/theme.toml`
   - `[map]` に `map_detail_zoom = 0` とコメントを追記。
5. ドキュメント
   - `SPEC.md` §6.1.2 に本設定を追記。docs/history plan/result・CHANGELOG を更新。

## 検証方法

- colors 単体: クランプ（99→19, -5→0, bool→無視）、`theme_toml_text` に行が出ること。
- folium 生成物: `build_map()` の HTML で `detail>0` のとき
  `maxNativeZoom`/`minNativeZoom` が固定値（ベースマップ上限へクランプ）で出ること。
- アプリ手動: 設定→保存→ズームで粒度が一定、0 で従来挙動に戻ることを目視。

## スコープ外・留意点

- ダウンロードPNGは対象外。
- 粒度を大きく下回るズームアウトでは native ズームのタイルを多数取得するため描画負荷が
  上がり得るが、店舗中心・半径円に収まるズーム域が主のため実用上許容。
