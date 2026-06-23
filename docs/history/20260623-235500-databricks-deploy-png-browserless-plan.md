# Databricks Apps デプロイ + PNG ブラウザレス化 計画

- 日時: 2026-06-23 23:55:00
- テーマ: Databricks Apps へのデプロイと、PNG 生成のブラウザレス化
- ブランチ: `main`（リポジトリ `github.com/canoekuro/mapsystem`）

## 目的

初期実装（SPEC v1.0）を Databricks Apps にデプロイする。ただし Databricks Apps の
ランタイムは root 権限が無く `apt-get` 不可で Chromium を導入できないため、selenium +
ヘッドレス Chrome に依存する PNG 生成（SC-01 画像DL・SC-02 画像ZIP）が動かない
（WebDriverException, chromedriver status 127）。ユーザー要件「PNG／画像ZIP は必須」
かつ「起動時間を最小化」を満たすため、PNG をブラウザ無しの純 Python 静的地図生成へ
置き換える。

## 対象ファイル

- `lib/static_map.py`（新規）: 純 Python（Pillow + requests）で OSM スリッピータイルを
  HTTP 取得し、Web Mercator 投影で半径円・番号付き色分けマーカー・店舗マーカー・凡例を
  描画して地図PNGを返す `render_static_map(store_row, facilities_df, radius_km, size=656)`。
- `lib/png_builder.py`: `_map_to_png`（selenium）を削除し、`build_png` を
  `compose_canvas(render_static_map(...), ...)` に変更。`compose_canvas`（1280×720 合成）は
  無改修で維持。
- `requirements.txt`: `selenium>=4,<5` を削除、`requests>=2,<3` を追加。
- `app.yaml`: Databricks Apps 仕様へ修正（後述）。
- `README.md` / `CHANGELOG.md` / `docs/history/`: 記録更新。

## 方針

- ブラウザも追加の重い依存も使わない（依存は既存の Pillow + requests のみ）ため、
  コンテナ起動は通常の pip インストールのみで高速（最小起動時間の解）。
- 画面内の対話地図（`st_folium`/folium）はクライアント側描画のため変更しない。
  差し替えるのは「ダウンロード用 PNG」の地図生成元のみ。
- タイル取得は env で上書き可能（`OSM_TILE_URL` / `MAP_TILE_USER_AGENT` / `MAP_TILE_TIMEOUT`）。
- `app.yaml`: Databricks Apps はコマンドをシェルで実行しないため `${VAR}` 展開不可。
  `command: ["streamlit","run","app.py"]` のみとし、ポートはランタイム自動注入に委ね、
  `STREAMLIT_SERVER_ADDRESS=0.0.0.0` ほか CORS/XSRF/usage-stats を env で設定。

## SPEC 逸脱

SPEC §8.3 は「folium._to_png の地図をリサイズ貼付」を前提とするが、no-browser 制約により
自前の静的地図画像へ置換する。最終成果（ヘッダー帯＋OSM地図＋半径円＋番号付き色分け
マーカー＋凡例＋施設リストの 1280×720 合成）と視覚的意図・レイアウト・色・寸法は維持。

## 検証方法

1. `render_static_map` と `build_png` をローカルで実 OSM タイルにより生成・目視
   （基図／半径円／番号付き色分けマーカー／店舗マーカー／凡例／日本語フォント）。
2. selenium 参照がコードから消えていることを確認。
3. `build_png_zip` のZIP生成を確認。
4. Databricks へ sync → `databricks apps deploy` → `databricks apps get` で RUNNING を確認。

## 記録方針

- 本 plan と対の result を保存し、`CHANGELOG.md` にリンク付きで追記する
  （`.agents/rules/plan-before-modify.md`）。
