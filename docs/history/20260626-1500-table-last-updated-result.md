# 結果: テーブル最終更新日時の表示（両ページ）

- 日時: 2026-06-26 15:00
- テーマ: table-last-updated
- 対応する計画: [20260626-1500-table-last-updated-plan.md](20260626-1500-table-last-updated-plan.md)

## 変更内容

### `lib/data.py`

- `load_table_last_updated() -> str | None` を追加（`@st.cache_data(ttl=300,
  show_spinner=False)`）。
  - `_table_and_spark()` を再利用し `DESCRIBE HISTORY {table}` を取得。
  - `operation` をデータ更新操作のホワイトリスト（WRITE / MERGE / UPDATE / DELETE /
    TRUNCATE / COPY INTO / STREAMING UPDATE / CREATE TABLE AS SELECT /
    REPLACE TABLE AS SELECT / CREATE OR REPLACE TABLE AS SELECT）で絞り込み、
    `max(timestamp)` を取得（OPTIMIZE/VACUUM 等の保守操作は除外）。
  - tz-naive は UTC とみなして `Asia/Tokyo` へ変換し `%Y-%m-%d %H:%M` で整形。該当なし／
    NaT は `None`。
  - `pyspark.sql.functions` は関数内で遅延 import。

### `app.py`

- `_render_last_updated()` を追加。`load_table_last_updated()` を呼び、成功時は
  `st.caption("データ最終更新: {ts}（JST）")`、例外／None 時は `logger.warning` の上で
  `st.caption("データ最終更新: 取得できませんでした")`。
- `main()` 内、`st.set_page_config` の後・`st.navigation(...).run()` の前に
  `_render_last_updated()` を呼び、両ページ共通の本文上部に表示。
- import を `from lib.data import load_company_names, load_table_last_updated` に更新し、
  `logger = logging.getLogger(__name__)` を追加。

## 検証結果

- 構文パース（`app.py` / `lib/data.py`）→ **OK**。
- UTC→JST 変換ロジックの単体確認（標準ライブラリ等価実装）→ **PASS**（UTC 05:30 → JST 14:30）。
- `import lib.data` / streamlit 起動は `pandas` / `streamlit` 未導入のため本環境では未実施
  （構文パスは確認済み。`pyspark` は遅延 import）。

## 未対応事項

- Databricks 実接続での表示確認（最新データ更新日時の JST 表示、保守操作の除外、参照不可時の
  フォールバック表示）は接続環境が必要なため未実施。
- `DESCRIBE HISTORY` の保持期間（既定30日）を超えるとデータ更新操作が履歴から消え、`None`
  （取得できませんでした）になり得る。通常運用（定期ジョブ更新）では問題なし。
