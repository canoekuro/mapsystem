# 計画: マップの固定画面化と「マップをリセット」ボタンの廃止

## 変更の目的

対話地図（`st_folium` + folium）の拡大縮小・移動を廃止し、初期表示のまま動かせない
「固定画面」にする。これにより誤操作（パン/ズーム）が起きなくなるため、誤操作からの復帰用
だった「マップをリセット」ボタンとその再マウント機構（`map_nonce`）を廃止する。

## 対象ファイル

- `lib/map_builder.py` — `build_map()` の `folium.Map(...)` に操作無効オプションを追加。
- `views/main_page.py` — 「マップをリセット」ボタン・`map_nonce` を削除し、`st_folium` の
  `key` から nonce を除去。
- `app.py` — `_render_last_updated()` で確保していたリセットボタン用の左列スロット
  （`_top_action_slot`）を廃止し、更新日時キャプションの列分割を簡素化。
- `SPEC.md` §6.1.2 左カラム（地図）— 固定画面仕様へ改訂、リセットボタン記述を削除。
- 記録: `docs/history/` に plan/result、`CHANGELOG.md` に追記。

## 具体的な変更内容

1. `folium.Map(...)` に以下を追加（Leaflet 操作系を全 off）:
   `zoom_control=False, dragging=False, scrollWheelZoom=False, doubleClickZoom=False,
   touchZoom=False, boxZoom=False, keyboard=False`。初期中心/ズーム（`zoom_for_radius`）で固定。
2. `views/main_page.py`: リセットボタンブロックと `nonce` 変数を削除。
   `st_folium(..., key=f"map_{store}_{loaded_fetch_radius}")`。
3. `app.py`: `st.columns` による左列確保をやめ、`st.markdown` で更新日時を右寄せ表示のみ。
   `st.session_state["_top_action_slot"]` の設定を削除。

## 検証方法

- `python -m py_compile` で構文確認。
- folium 0.20 で対象オプションが `L.map(...)` に `false` として出力されることを確認。
- 残存参照（`_top_action_slot` / `map_nonce` / `reset_map` / `nonce`）が無いことを grep で確認。
