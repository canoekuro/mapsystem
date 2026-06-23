# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### 2026-06-23

- feat: SPEC v1.0 準拠のマップアプリ（Streamlit + folium、Databricks Apps 向け）を新規構築。
  SC-01 店舗周辺マップ／SC-02 企業一括出力／SC-03 ヘルプの 3 画面、PNG 合成・ZIP 出力を実装。
  [詳細](docs/history/20260623-224035-mapapp-initial-plan.md) /
  [結果](docs/history/20260623-224035-mapapp-initial-result.md)
- feat: PNG 生成をブラウザレス化（selenium 撤去、`lib/static_map.py` で純 Python の OSM
  タイル合成）。Databricks Apps（Chromium 導入不可）でも画像 DL／画像 ZIP が動作。
  [詳細](docs/history/20260623-235500-databricks-deploy-png-browserless-plan.md) /
  [結果](docs/history/20260623-235500-databricks-deploy-png-browserless-result.md)
- build: Databricks Apps へデプロイ（アプリ名 `mapsystem`）。`app.yaml` をランタイム仕様に
  修正（`${VAR}` 非展開を回避し、ポートはランタイム自動注入・設定は env 化）。
