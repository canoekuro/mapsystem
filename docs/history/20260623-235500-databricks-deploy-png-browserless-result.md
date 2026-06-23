# Databricks Apps デプロイ + PNG ブラウザレス化 結果

- 日時: 2026-06-23 23:55:00（着手）/ 同日完了
- テーマ: Databricks Apps へのデプロイと、PNG 生成のブラウザレス化
- 対応する計画: [20260623-235500-databricks-deploy-png-browserless-plan.md](20260623-235500-databricks-deploy-png-browserless-plan.md)

## 変更内容

- `lib/static_map.py`（新規）: 純 Python（Pillow + requests）による静的地図生成
  `render_static_map(store_row, facilities_df, radius_km, size=656)` を追加。OSM タイルを
  HTTP 取得（`@lru_cache` で重複排除）→ Pillow で連結・クロップ → Web Mercator 投影で
  半径円（測地多角形＋半透明塗り）・番号付き色分けマーカー・店舗マーカー・凡例を描画。
- `lib/png_builder.py`: `_map_to_png`（selenium / ヘッドレス Chrome）を削除。`build_png` を
  `compose_canvas(render_static_map(...), ...)` に変更。冒頭 docstring も更新。
  `compose_canvas`（1280×720 合成）は無改修。
- `requirements.txt`: `selenium>=4,<5` を削除、`requests>=2,<3` を追加。
- `app.yaml`: `command: ["streamlit","run","app.py"]` のみとし、`STREAMLIT_SERVER_ADDRESS=0.0.0.0`
  / `STREAMLIT_SERVER_HEADLESS=true` / `STREAMLIT_SERVER_ENABLE_CORS=false` /
  `STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false` / `STREAMLIT_BROWSER_GATHER_USAGE_STATS=false`
  を env で設定。
- `README.md`: PNG のブラウザ不要化、実行時 OSM egress 要件、デプロイ手順、ファイル構成
  （`lib/static_map.py`）を更新。

## デプロイ経緯（学び）

- 初回・2回目のデプロイは `app crashed unexpectedly`（FAILED）。原因は当初 app.yaml の
  `--server.port "${DATABRICKS_APP_PORT:-8000}"`。Databricks Apps は **command をシェルで
  実行しない**ため `${...}` が展開されず、不正なポート文字列で Streamlit がクラッシュ。
  PAT 認証では `databricks apps logs`（OAuth 必須）が使えないため、公式ドキュメントで
  挙動を確認し、`--server.*` フラグを廃して env 設定に変更して解決。
- 3回目で `App started successfully`（RUNNING）。
- その後、PNG をブラウザレス化して再デプロイし RUNNING を確認。

## 検証結果

- ローカル: `render_static_map` が 656×656、`build_png` が 1280×720 を実 OSM タイルで生成し
  目視確認（基図・半径円・番号付き色分けマーカー・店舗マーカー・凡例・施設リスト・
  「他N件」・日本語フォント）。`build_png_zip` のZIP生成も確認。
- selenium 参照はコード本体から消去（docstring も更新）。
- Databricks Apps: アプリ名 `mapsystem`、URL
  `https://mapsystem-130773044949419.aws.databricksapps.com`、state=RUNNING を確認。

## 未対応事項・既知リスク

- **実行時 OSM タイル egress 依存**: APP コンテナから OSM タイルサーバへ HTTP 到達できる
  必要がある。ブロック時は `OSM_TILE_URL` 等の env で差し替え。Databricks 上での PNG 実DL
  動作はユーザーによるブラウザ確認が必要（PAT ではログ取得不可）。
- **一括出力の規模**: Databricks Apps のリクエスト 120 秒上限により、多店舗企業の画像 ZIP は
  超過し得る。超大規模は将来 Lakeflow Job 化を検討（本タスク範囲外）。
- `data/master.csv` はサンプル。本番は同スキーマの実データへ差し替え。
