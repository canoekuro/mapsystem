# 計画: テーブル最終更新日時の表示（両ページ）

- 日時: 2026-06-26 15:00
- テーマ: table-last-updated

## 背景・目的

データアップロード機能でユーザーが Volume へファイルを格納すると Databricks ジョブが
テーブルを更新するが、ユーザーは「データが最後にいつ更新されたか」をアプリ上で確認できない。
アップロード後のジョブ反映の目安にもなるため、マップ／データ更新の両ページにテーブルの
最終更新日時を表示する。

更新日時の定義: **最後のデータ更新**。`DESCRIBE HISTORY` から WRITE/MERGE/UPDATE/DELETE 等の
データ更新操作のみを対象に最新タイムスタンプを採用する（OPTIMIZE/VACUUM 等の保守操作は除外）。

## 対象ファイル

- `lib/data.py` — `load_table_last_updated()` 追加。
- `app.py` — 共通キャプション描画を追加。

## 変更内容

- `lib/data.py`: `@st.cache_data(ttl=300, show_spinner=False)` の `load_table_last_updated()`
  を追加。`_table_and_spark()` を再利用し、`DESCRIBE HISTORY {table}` をデータ更新操作の
  ホワイトリストで絞り込み、`max(timestamp)` を取得。tz-naive は UTC とみなして Asia/Tokyo へ
  変換し `%Y-%m-%d %H:%M` で整形。該当なしは `None`。
- `app.py`: `_render_last_updated()` を追加し、`st.navigation(...).run()` の前に呼ぶ
  （run 前の要素は全ページ共通表示）。例外は握りつぶして「取得できませんでした」を表示し、
  テーブル参照不可でもデータ更新ページが使えるようにする。import に
  `load_table_last_updated` を追加。

## 検証方法

- `app.py` / `lib/data.py` の構文パース。
- UTC→JST 変換ロジックの単体確認（UTC 05:30 → JST 14:30）。
- streamlit 起動で両ページ上部に「データ最終更新: …（JST）」が出ること（要 streamlit）。
- 実接続で最新データ更新日時が JST 表示され、保守操作が除外されること（要 Databricks）。
