# 計画：ローカルCSV → Databricks Volume テーブル参照への移行

## 目的

データの大規模化に備えて、`data/master.csv` へのローカル読み込みを廃止し、
Databricks Unity Catalog テーブルを Spark 経由で参照するよう変更する。

## 対象ファイルと変更内容

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `lib/data.py` | 変更 | `load_master()` を `DatabricksSession.builder.getOrCreate()` + `spark.table()` に置き換え |
| `config/databricks_config.toml` | 新規 | テーブル名プレースホルダーを含む設定ファイル |
| `requirements.txt` | 変更 | `databricks-connect>=14.0` を追加 |
| `SPEC.md` | 変更 | §4.1（ファイル仕様）・§8.1（マスタロード）をテーブル参照仕様に更新 |
| `docs/history/20260625-0900-volume-table-reference-result.md` | 新規 | 実施結果の記録 |
| `CHANGELOG.md` | 変更 | Unreleased セクションに本変更を追記 |

## 検証方法

- `lib/data.py` の import/型アノテーションに変更なし（既存インタフェース維持）
- `app.py` の `load_master()` 呼び出しはそのまま動作する
- Databricks Apps 環境では `DatabricksSession.builder.getOrCreate()` がクレデンシャル自動取得
- ローカル開発時は `~/.databrickscfg` または環境変数でクレデンシャル設定
