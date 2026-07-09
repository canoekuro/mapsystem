# 計画: 対話地図サイズをテーマ設定ページから調整可能にする

- 日付: 2026-07-09

## 目的・背景

対話地図（画面内 `st_folium`）のサイズは `views/main_page.py` と `lib/map_builder.py` に
`width=700` / `height=560` としてハードコードされ、変更時に2箇所を手で揃える必要があった。
配色・地図背景と同様に「テーマ設定」ページから調整できるようにする。既存のテーマ基盤
（`config/theme.toml` `[map]` ＋ `lib/colors.py` ＋ `views/config_page.py`）に `map_width` /
`map_height` を追加し、描画時に解決させることで両者を1設定で一致させる。

スコープは画面内の対話地図のみ。ダウンロードPNG（固定レイアウト）は対象外。UIは幅・高さの
個別 `st.number_input`。

## 対象ファイルと変更内容

- `config/theme.toml`: `[map]` に `map_width = 700` / `map_height = 560` を追記。
- `lib/colors.py`: `_DEFAULTS` に map_width/map_height、`_load_from_file` で `[map]` から読込、
  `_merge` に整数クランプ分岐（`[200, 2000]`）、アクセサ `map_width()` / `map_height()`、
  `theme_toml_text` の `[map]` 出力を追加。
- `lib/map_builder.py`: `folium.Map(width/height)` と `zoom_for_radius(viewport_px=...)` を
  `map_width()` / `map_height()` で解決。
- `views/main_page.py`: `st_folium(width/height)` を `map_width()` / `map_height()` に。
- `views/config_page.py`: 「地図サイズ（画面表示）」セクションに number_input 2つ、
  `_init_state` / `_collect_values` / `_reset_to_default` に map_width/map_height を追加。
- `SPEC.md`: §6.1.2 サイズ記述、§6.4 調整対象（地図サイズ）を更新。
- `CHANGELOG.md`: `### 2026-07-09` に feat を追記。

## 再利用する既存資産

- `lib/colors.py` のテーマ配管（`_DEFAULTS`/`_load_from_file`/`_merge`/`theme_toml_text`/
  `save_theme`/`get_theme`）。`[map]` は basemap で実績あり。
- `views/config_page.py` の `_init_state`/`_collect_values`/`_reset_to_default` 3点セット。
- `lib/data.zoom_for_radius`（`viewport_px` 引数で高さ連動）。

## 検証方法

- 構文チェック（`ast.parse`）。
- アクセサ単体: 既定 700/560、theme.toml で 900/700 → 反映、範囲外/非数値はクランプ/フォールバック、
  `theme_toml_text` に map_width/map_height が含まれること。テスト後に既定へ復元。
- UI（可能なら `streamlit run`。テーマ設定タブは既定非表示のため一時的に show_theme_page=true）。

## 影響・非互換

- 既定 700×560 で見た目は不変。ダウンロードPNGのサイズは変わらない。
