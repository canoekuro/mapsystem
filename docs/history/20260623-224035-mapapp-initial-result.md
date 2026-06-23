# マップアプリ初期実装 結果

- 日時: 2026-06-23 22:40:35（着手） / 同日 完了
- テーマ: SPEC v1.0 準拠のマップアプリ新規構築
- ブランチ: `feat/map-app-initial`
- 対応する計画: [20260623-224035-mapapp-initial-plan.md](20260623-224035-mapapp-initial-plan.md)

## 変更内容

SPEC §9 のファイル構成を新規作成した。

- `requirements.txt`: streamlit/pandas/folium/streamlit-folium/selenium/Pillow（SPEC §3）。
- `scripts/gen_sample.py` + `data/master.csv`: 名古屋圏 3 企業 10 店舗、各店舗 14〜24 施設、
  Haversine で距離事前算出、近接バイアスで 2km 圏内に多数配置（計 195 行）。`random.seed(42)`。
- `fonts/ipaexg.ttf`: IPAexゴシック（6,041,284 バイト、TTF マジック・Pillow 読込で真正性確認）。
  公式配布元がブロックのため PyPI 配布の japanize-matplotlib 同梱物から取得。
- `lib/data.py`: `load_master`（`@st.cache_data`、例外伝播）、`store_names`/`company_names`、
  `filter_facilities`（SPEC §8.2 逐語、連番付与）、`zoom_for_radius`（§6.1.2 階段式）。
- `lib/map_builder.py`: `build_map`（Circle／店舗マーカー／BeautifyIcon 番号入り色分け
  マーカー／右下凡例。0 件でも例外なし）。
- `lib/png_builder.py`: `_map_to_png`（headless Chrome、container-safe フラグ）、
  `compose_canvas`（純関数、1280×720 合成、カード溢れ「他N件」）、`build_png`。
- `lib/zip_builder.py`: `build_png_zip`（失敗店舗スキップ＋`errors.txt` 同梱、`progress_cb`）、
  `build_csv_zip`。
- `pages/map_single.py`（SC-01）/`map_bulk.py`（SC-02）/`help.py`（SC-03）、`app.py`。
- `app.yaml`（Databricks Apps）, `README.md`, `.gitignore`。

## 検証結果

- 依存インストール成功（streamlit 1.58 / pandas 2.3.3 / folium 0.20 / streamlit-folium
  0.27.2 / selenium 4.45 / Pillow 10.4）。
- `gen_sample.py`: 195 行生成。各店舗 2km 圏内 10〜17 件（「他N件」溢れ条件を満たす）。
- `lib/data.py`: 絞込件数・距離昇順・連番 1 始まり・ズーム階段（16/15/13/12）を確認。
- `lib/map_builder.py`: HTML 生成・Circle・マーカー・凡例文字列・0 件 render を確認。
- `compose_canvas`: overflow／few／zero の 3 ケースで 1280×720 生成・目視確認
  （ヘッダー帯・色分けバッジ・`約X.Xkm`・「他 7 件」・日本語フォント）。
- `build_png` 全経路: headless Chrome + 実 OSM タイルで 685,980 バイトの合成 PNG 生成成功
  （地図・半径円・店舗/施設マーカー・凡例・ヘッダー・施設リストすべて描画）。
- `build_png_zip`/`build_csv_zip`: ZIP メンバー・`progress_cb` 呼出を確認。
- `streamlit run app.py` headless 起動: HTTP 200 / health 200、起動ログにエラーなし。

## 受入条件（SPEC §12）対応

- SC-01 地図・施設リスト表示 / PNG DL / CSV DL: 実装・検証済み。
- SC-02 画像 ZIP / データ ZIP: 実装・検証済み。
- SC-03 出典表示: SPEC §6.3 全文一致を確認。
- Databricks Apps 起動: `app.yaml` 用意。実機起動は未実施（下記）。

## 未対応事項・既知リスク

- Databricks Apps 実機での起動・PNG 経路の動作確認は未実施。ランタイムに Chrome/Chromium
  本体が無い場合は PNG／画像 ZIP が動作しないため、ベースイメージ導入または `CHROME_BIN`
  指定が必要（README「デプロイ時の留意事項」、`app.yaml` コメントに記載）。
- `data/master.csv` はサンプル。本番は同スキーマの実データへ差し替え。
