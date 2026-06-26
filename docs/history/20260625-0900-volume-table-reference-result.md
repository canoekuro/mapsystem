# 結果：ローカルCSV → Databricks Volume テーブル参照への移行

## 変更内容

### `lib/data.py`
- `load_master()` を `pd.read_csv("data/master.csv")` から `spark.table(table_name).toPandas()` に変更
- `_load_databricks_config()` 関数を追加（`config/databricks_config.toml` を読み込む）
- `DatabricksSession` は `load_master()` 内で遅延 import（`st.cache_data` の初回呼び出し時のみ起動）
- 既存の列名マッピング（`column_mapping.toml`）はそのまま維持

### `config/databricks_config.toml`（新規）
- `[databricks] table = "catalog.schema.table_name"` のプレースホルダーを設定
- 実際のデプロイ前に正しいテーブル名へ変更すること

### `requirements.txt`
- `databricks-connect>=14.0` を追加

### `SPEC.md`
- §4.1: ファイル仕様 → Unity Catalog テーブル仕様に更新
- §8.1: マスタロードのコード例を Spark 版に更新
- §9: ファイル構成を更新（`data/master.csv` 削除、`config/databricks_config.toml` 追加）

## 動作確認の前提

- Databricks Apps 上では `DatabricksSession.builder.getOrCreate()` がクレデンシャルを自動取得
- ローカル開発時は `~/.databrickscfg` または環境変数 `DATABRICKS_HOST` / `DATABRICKS_TOKEN` を設定

## 未対応事項

- `config/databricks_config.toml` のテーブル名は仮プレースホルダー（`catalog.schema.table_name`）のまま
  → 実際のデプロイ前に運用担当者が正しい 3 パート名に変更すること
- `data/master.csv` は削除せずリポジトリに残す（開発・検証用途で参照される可能性があるため）
