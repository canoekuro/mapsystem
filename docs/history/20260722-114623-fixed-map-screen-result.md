# 結果: マップの固定画面化と「マップをリセット」ボタンの廃止

## 変更内容

- `lib/map_builder.py`: `build_map()` の `folium.Map(...)` に操作無効オプションを追加。
  `zoom_control=False` / `dragging=False` / `scrollWheelZoom=False` / `doubleClickZoom=False` /
  `touchZoom=False` / `boxZoom=False` / `keyboard=False`。初期中心/ズーム（`zoom_for_radius`）の
  ままパン/ズーム不可の固定画面になった。
- `views/main_page.py`: 「マップをリセット」ボタンと `map_nonce` を削除。`st_folium` の `key` を
  `f"map_{store}_{loaded_fetch_radius}"`（nonce 除去）に変更。
- `app.py`: `_render_last_updated()` の左列スロット確保（`st.columns` + `_top_action_slot`）を廃止し、
  更新日時キャプションを `st.markdown` の右寄せ表示のみへ簡素化。
- `SPEC.md` §6.1.2 左カラム（地図）: 固定画面仕様へ改訂し、リセットボタン記述を削除。

## 検証結果

- `python -m py_compile app.py lib/map_builder.py views/main_page.py` — OK。
- folium 0.20.0 で対象7オプションが `L.map(...)` に `false` として出力されることを確認。
- `_top_action_slot` / `map_nonce` / `reset_map` / `reset_slot` / `nonce` のコード内残存参照が
  無いことを grep で確認（docs/history の過去記録を除く）。

## 未対応事項

- ダウンロードPNG（`lib/static_map.py`）は元々静止画のため変更不要。
- 実機（Streamlit / Databricks Apps）での目視確認は本環境では未実施。ローカル起動時に
  ドラッグ・ホイールズームが効かず、＋/− ボタンとリセットボタンが無いことを確認すること。
