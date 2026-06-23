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

### 2026-06-24

- refactor: マルチページ（ラジオ）を廃止し**単一ページ**へ集約（`views/main_page.py`）。
  上部に企業→小売店カスケード選択＋半径、企業一括データ（cp932 CSV）/画像（ZIP）DL、
  下部に地図＋施設リスト、最下部に出典を小さく表示。店舗単位DL（旧F-02/F-03）は廃止。
  [詳細](docs/history/20260624-0040-issues-202606240034-plan.md) /
  [結果](docs/history/20260624-0040-issues-202606240034-result.md)
- fix: 半径円が地図／PNG に表示されるよう、`zoom_for_radius` を「円がビューポートに収まる
  動的ズーム」へ変更（段階式を廃止）。
- feat: 企業一括を「データ抽出（単一CSV cp932）」と「画像抽出（PNG ZIP）」の2画面に分割。
  店舗ごとCSVのZIP（`build_csv_zip`）は廃止。
- refactor: Streamlit 自動マルチページ回避のため画面を `pages/` から `views/` へ移設し、
  サイドバーのナビをラジオのみに統一。
  [詳細](docs/history/20260624-0030-issues-202606240011-plan.md) /
  [結果](docs/history/20260624-0030-issues-202606240011-result.md)
