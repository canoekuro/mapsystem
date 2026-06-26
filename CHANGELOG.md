# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### 2026-06-26

- feat: テーブルの最終更新日時（最後のデータ更新）を全ページ上部に表示。`DESCRIBE HISTORY` から
  WRITE/MERGE/UPDATE/DELETE 等のデータ更新操作のみを抽出して最新タイムスタンプを JST 表示し
  （OPTIMIZE/VACUUM 等の保守操作は除外）、アップロード後のジョブ反映の目安にできるようにした。
  [詳細](docs/history/20260626-1500-table-last-updated-plan.md) /
  [結果](docs/history/20260626-1500-table-last-updated-result.md)
- feat: データ更新（アップロード）機能を追加。`st.navigation` でマルチページ化し、別ページで
  推進園・店舗の Excel をアップロードして「更新」押下時に Unity Catalog Volume へ格納する。
  各ファイルは固定名（`nursery.xlsx` / `store.xlsx`）に変換され、格納先フォルダ内の既存ファイルを
  置き換える。片方のみのアップロードにも対応（その側のフォルダのみ更新）。テーブル更新は
  Databricks ジョブ側の責務とする。
  [詳細](docs/history/20260626-1400-data-upload-plan.md) /
  [結果](docs/history/20260626-1400-data-upload-result.md)
- feat: データ取得時に取得件数サマリを表示。取得後は常時、取得した行数と選択肢になる
  店舗数を表示し（非0件は `st.success`、0件は「取得処理は成功しています」と明示した
  `st.warning`）、0件のときに取得失敗と区別できない問題を解消した。
  [詳細](docs/history/20260626-1200-fetch-count-display-plan.md) /
  [結果](docs/history/20260626-1200-fetch-count-display-result.md)
- feat: データ取得をオンデマンド方式へ変更。起動時は企業名称の DISTINCT のみを取得し、
  企業名称＋取得半径を指定して「データ取得」を押下したときに `企業名称 == 指定企業 AND
  距離km <= 取得半径` を Spark 側で適用して取得する（`load_master()` の全件ロードを廃止）。
  取得用半径と表示用半径を分離し、取得済みデータを表示半径（取得半径以下）でインメモリ絞込
  できるようにした（例: 5km で取得して 2km で表示）。
  [詳細](docs/history/20260626-0500-on-demand-fetch-plan.md) /
  [結果](docs/history/20260626-0500-on-demand-fetch-result.md)

### 2026-06-25

- feat: データソースをローカル `data/master.csv` から Databricks Unity Catalog テーブルへ移行。
  `DatabricksSession.builder.getOrCreate()` + `spark.table()` による読み込みに変更し、
  テーブル名は `config/databricks_config.toml` で管理。大規模データへの対応強化。
  [詳細](docs/history/20260625-0900-volume-table-reference-plan.md) /
  [結果](docs/history/20260625-0900-volume-table-reference-result.md)

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

- feat: 企業一括ダウンロードの並びを「データダウンロード → 都道府県で絞り込み → 画像をダウンロード」
  に変更し、データボタン名を「データダウンロード」に。地図に「マップをリセット」ボタンを追加
  （誤操作時に初期表示へ復帰）。
  [詳細](docs/history/20260624-0800-issues-ui-tweaks-plan.md) /
  [結果](docs/history/20260624-0800-issues-ui-tweaks-result.md)
- feat: PNG に「対象推進園数 N件」帯を追加（ヘッダー帯と地図の間。画面の並びと一致）。
  企業一括DLを企業名称直下の折りたたみ（`st.expander`）へ集約し、画像DLは**都道府県絞り込み**
  （選択企業で絞込・未選択時は無効＝大量DL防止）＋ `@st.cache_data` で**1ボタン**化。
  `master.csv` に `都道府県` 列を追加。
  [詳細](docs/history/20260624-0645-issues-2020606240638-plan.md) /
  [結果](docs/history/20260624-0645-issues-2020606240638-result.md)
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
