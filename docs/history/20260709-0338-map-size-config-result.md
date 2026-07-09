# 結果: 対話地図サイズをテーマ設定ページから調整可能にする

- 日付: 2026-07-09
- 対象計画: `docs/history/20260709-0338-map-size-config-plan.md`

## 変更内容

- `config/theme.toml`: `[map]` に `map_width = 700` / `map_height = 560` を追記。
- `lib/colors.py`:
  - `_DEFAULTS` に `map_width: 700` / `map_height: 560`、許容範囲定数 `_MAP_SIZE_MIN=200` /
    `_MAP_SIZE_MAX=2000` を追加。
  - `_load_from_file` で `[map]` から `basemap` に加え `map_width` / `map_height` を読込。
  - `_merge` に `map_width` / `map_height` の整数クランプ分岐（`int/float` かつ正、`[200,2000]`）。
  - アクセサ `map_width() -> int` / `map_height() -> int` を追加。
  - `theme_toml_text` の `[map]` 出力に map_width / map_height を追加。
- `lib/map_builder.py`: `folium.Map(width/height)` と `zoom_for_radius(viewport_px=...)` を
  `map_width()` / `map_height()` で解決。
- `views/main_page.py`: `st_folium(width/height)` を `map_width()` / `map_height()` に。
- `views/config_page.py`: 「地図サイズ（画面表示）」セクションに幅・高さの `st.number_input`
  （幅 500–1200 / 高さ 400–1000、step 20）、`_init_state` / `_collect_values` /
  `_reset_to_default` に map_width / map_height を追加。
- `SPEC.md`: §6.1.2（サイズはテーマで調整可・既定 700×560）、§6.4（調整対象に地図サイズ）を更新。
- `CHANGELOG.md`: `### 2026-07-09` に feat を追記。

## 検証結果

- 構文チェック（`ast.parse`）: `lib/colors.py` / `lib/map_builder.py` / `views/main_page.py` /
  `views/config_page.py` OK。
- アクセサ単体:
  - 既定で `map_width()==700` / `map_height()==560`。
  - `[map] map_width=900 / map_height=700` → `900` / `700` を返す。
  - 範囲外（`map_width=5000`）は `2000` にクランプ、非数値（`map_height="big"`）は既定 `560` へ
    フォールバック。
  - `theme_toml_text(get_theme())` に `map_width` / `map_height` を含む。
  - テスト後に `config/theme.toml` を既定（700/560）へ復元済み。

## 未対応事項・備考

- Databricks 接続を伴う `streamlit run` の end-to-end 動作確認は資格情報制約により未実施。
  テーマ設定ページは既定非表示（`config/app_config.toml` `show_theme_page=false`）のため、
  画面確認時は一時的に `true` にする必要がある。
- ダウンロードPNG（合成キャンバス 1280×720・地図領域 656×616）のサイズは今回対象外で不変。
