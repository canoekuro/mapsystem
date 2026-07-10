# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### 2026-07-10

- feat: 対話地図の表示情報の粒度（詳細度）をズーム操作から切り離して固定できるように。
  `config/theme.toml` `[map] map_detail_zoom`（既定 0=固定しない、1–19=その粒度で固定）を
  追加し「テーマ設定」ページから調整可能に。`lib/map_builder.py` で `folium.TileLayer` の
  `max_native_zoom`/`min_native_zoom` を同値（ベースマップの `max_zoom` へクランプ）に設定して
  実現。対象は対話地図のみ（ダウンロードPNGは対象外）。`lib/colors.map_detail_zoom()` を新設。
  [詳細](docs/history/20260710-010914-fixed-detail-zoom-plan.md) /
  [結果](docs/history/20260710-010914-fixed-detail-zoom-result.md)

- feat: 地図の背景（ベースマップ）に OSMFJ（OpenStreetMap Foundation Japan）の
  日本語スタイルタイル（`osmfj_japan`）を追加。提供元グループは新設せず既存の
  「OpenStreetMap」にまとめる。`lib/basemaps.py` の `BASEMAPS` に定義を追加し、
  `config/theme.toml` のコメントの id 一覧も更新。
  [詳細](docs/history/20260710-003444-osmfj-basemap-plan.md) /
  [結果](docs/history/20260710-003444-osmfj-basemap-result.md)

### 2026-07-09

- feat: 対話地図（画面表示）のサイズ（幅・高さ px）を「テーマ設定」ページから調整可能に。
  `config/theme.toml` `[map] map_width`/`map_height` に保存し、`lib/colors.map_width()`/
  `map_height()` で描画時に解決して `st_folium`（`views/main_page.py`）と `folium.Map`
  （`lib/map_builder.py`）へ同一値を渡す（`zoom_for_radius` の基準も高さに連動）。既定は
  現行と同じ `700×560`。ダウンロードPNGのサイズは対象外。
  [詳細](docs/history/20260709-0338-map-size-config-plan.md) /
  [結果](docs/history/20260709-0338-map-size-config-result.md)

- refactor: 表示半径の設定を廃止し、取得半径をそのまま表示に使用（取得半径＝表示半径）。
  単一ページ画面から「表示半径」ウィジェットを撤去し、ヘッダー・件数・地図・施設リストは
  取得半径で描画する。SPEC §8.2 の二段絞り込み仕様を改訂。
  [詳細](docs/history/20260709-0255-issue20260709-radius-pref-configtab-plan.md) /
  [結果](docs/history/20260709-0255-issue20260709-radius-pref-configtab-result.md)

- feat: 小売店名称の絞り込みに都道府県（単一選択・任意）を追加。絞り込み順を
  `企業名称 → 取得半径 →（データ取得）→ 都道府県 → 小売店名称` とし、都道府県と小売店名称を
  横並び配置。都道府県未選択なら企業内の全店舗、選択でその県の店舗のみを候補にする。
  [詳細](docs/history/20260709-0255-issue20260709-radius-pref-configtab-plan.md) /
  [結果](docs/history/20260709-0255-issue20260709-radius-pref-configtab-result.md)

- feat: 「テーマ設定」タブの表示/非表示を `config/app_config.toml` の `[ui] show_theme_page`
  で切替可能に（既定は非表示）。`lib/app_config.py` を新設し、`app.py` はフラグが true の
  ときだけ「テーマ設定」ページを `st.navigation` に登録する。
  [詳細](docs/history/20260709-0255-issue20260709-radius-pref-configtab-plan.md) /
  [結果](docs/history/20260709-0255-issue20260709-radius-pref-configtab-result.md)

- refactor: 取得件数サマリを「取得結果: {行数}件（店舗数: {店舗数}）」から
  「取得店舗数: {店舗数}件」のみの表示に簡素化（0件時の文言も同様に変更）。
  [詳細](docs/history/20260709-0153-fetch-count-stores-only-plan.md) /
  [結果](docs/history/20260709-0153-fetch-count-stores-only-result.md)

- refactor: 単一ページ画面のダウンロードUIを整理。「企業一括ダウンロード」expander を
  「データダウンロード」に、その中の「データダウンロード」ボタンを「ローデータダウンロード」に
  改称。あわせて expander を小売店名称・表示半径の選択より上へ移動し、取得結果 → データ
  ダウンロード → 小売店名称／表示半径 の並びにした。

- fix: 半径円を地図に収める `zoom_for_radius` の目標占有率 `fraction` を 0.8 から 0.95 に
  引き上げ、小さい半径の縮尺を一段アップ。半径 1km・2km は対話地図でこれまでより一段
  ズームインして表示される（例: 緯度35度で 1km が z14→z15、2km が z13→z14）。3km 以上は
  従来どおり据え置き。`floor` 選択は維持しているため円の占有率は最大でも 95% に収まり、
  はみ出さない保証はそのまま。対話地図(folium)・ダウンロードPNG(static_map) の双方に反映。

### 2026-07-07

- feat: 地図の背景（ベースマップ）を「テーマ設定」ページから選択可能に。**OpenStreetMap**（標準/
  Humanitarian）・**国土地理院**（標準/淡色/航空写真/白地図）・**CARTO(OSMベース)**（Positron/Voyager/
  Dark Matter）を提供元→スタイルの2段セレクトで切替。既定値は `config/theme.toml` `[map] basemap` で指定。
  カタログは `lib/basemaps.py` に一元化し、対話地図(folium)・ダウンロードPNG(static_map) 双方へ反映。
  タイル提供元の帰属表示を地図/PNGに表示し、`zoom_for_radius` は各ベースマップの最大ズームでクランプ。
  [詳細](docs/history/20260707-1332-basemap-selector-plan.md) /
  [結果](docs/history/20260707-1332-basemap-selector-result.md)

- feat: 「テーマ設定」ページを追加し、配色を config から調整可能に。凡例（推進園区分）・
  半径円（線色＋塗り透明度）・見出し帯／施設リストヘッダー・店舗マーカーの色を `st.color_picker`
  で選び、`config/theme.toml` に保存すると地図とダウンロードPNGの双方へ反映される。配色は
  `lib/colors.py` のテーマに一元化し、各描画のハードコード（`#7C3AED` ×4 等）を撤去。店舗マーカーは
  任意の hex 色を指定できるよう `BeautifyIcon` 化。Databricks Apps は FS 揮発性のため保存の恒久化は
  「設定TOMLをダウンロード」→リポジトリにコミットで行う（UI で誘導）。
  [詳細](docs/history/20260707-1002-theme-config-page-plan.md) /
  [結果](docs/history/20260707-1002-theme-config-page-result.md)
- fix: 推進園区分の色分けを区別しやすい配色へ変更。認可保育所（緑）と認定こども園（黄）が
  紛らわしいという実機フィードバックを受け、色覚多様性にも配慮した高コントラストな3色
  （認可保育所=青 `#2A78D6` / 認定こども園=橙 `#EB6834` / 幼稚園=紫 `#4A3AA7`）へ更新。
  紛らわしかった2区分は最も分離の大きい色対（青↔橙）へ割り当て。色定義は一元化済みのため
  `lib/colors.py` の変更が全描画へ反映される。配色は validate_palette で検証（全チェック PASS）。
  [詳細](docs/history/20260707-0936-color-contrast-improvement-plan.md) /
  [結果](docs/history/20260707-0936-color-contrast-improvement-result.md)
- feat: 推進園区分の色分け凡例（認可保育所 / 認定こども園 / 幼稚園）を地図左下に表示。
  インタラクティブ地図（folium）は HTML 凡例を重ね、ダウンロード/静的PNG は地図画像へ
  凡例を焼き込む。あわせて4箇所（`map_builder` / `png_builder` / `static_map` / `main_page`）に
  重複していた色定義を `lib/colors.py` に一元化し、区分名ドリフトの再発を防止。SPEC §6.1.2 を更新。
  [詳細](docs/history/20260707-0935-legend-and-color-consolidation-plan.md) /
  [結果](docs/history/20260707-0935-legend-and-color-consolidation-result.md)

- feat: `推進園区分`（`認可保育所` / `認定こども園` / `幼稚園`）による地図・施設リストの色分けを
  実データに整合。色分けテーブル（`map_builder` / `png_builder` / `static_map` / `main_page` の
  4箇所）が旧区分名をキーにしており `認可保育所` / `認定こども園` がフォールバック色に落ちて
  いた不具合を修正（緑=認可保育所 / 黄=認定こども園 / 赤=幼稚園）。あわせてサンプル生成
  （`gen_sample.py` / `master.csv`）と SPEC を実値へ整合。凡例は追加しない。
  [詳細](docs/history/20260707-0906-suisinen-category-color-plan.md) /
  [結果](docs/history/20260707-0906-suisinen-category-color-result.md)

### 2026-06-29

- fix: 地図の凡例（保育園 / 幼稚園 / こども園）を画面の地図とダウンロードPNGの両方から削除。
  実データに推進園区分の実フラグが無く全マーカーがフォールバック色になるため、凡例が
  意味をなしていなかった。色分けロジック自体は残置。あわせて施設リスト・マーカー tooltip・
  PNG の距離表示をフル精度から小数第2位（`約0.30km`）へ丸めるよう変更し、SPEC を実態へ整合。
  [詳細](docs/history/20260629-1519-issue-202606291519-plan.md) /
  [結果](docs/history/20260629-1519-issue-202606291519-result.md)

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
