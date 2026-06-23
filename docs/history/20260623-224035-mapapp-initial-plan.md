# マップアプリ初期実装 計画

- 日時: 2026-06-23 22:40:35
- テーマ: SPEC v1.0 準拠のマップアプリ新規構築
- ブランチ: `feat/map-app-initial`

## 目的

`SPEC.md`（マップアプリ 実装仕様書 v1.0、§1〜§12）に基づき、担当小売店周辺の施設
（推進園）を地図上に可視化し、PNG／CSV／ZIP で出力する Streamlit + folium アプリを
新規構築する。デプロイ先は Databricks Apps。リポジトリは実質グリーンフィールドのため
SPEC §9 のファイル構成をそのまま新規作成する。

## 対象ファイル

- `requirements.txt`（SPEC §3）
- `scripts/gen_sample.py` → `data/master.csv`（SPEC §4.2 のサンプル）
- `fonts/ipaexg.ttf`（IPAexゴシック、IPA Font License）
- `lib/data.py`（SPEC §8.1/§8.2/§6.1.2）
- `lib/map_builder.py`（SPEC §6.1.2）
- `lib/png_builder.py`（SPEC §8.3、取得 `_map_to_png` と合成 `compose_canvas` を分離）
- `lib/zip_builder.py`（SPEC §6.2.2/§8.4/§11）
- `pages/map_single.py`（SC-01）, `pages/map_bulk.py`（SC-02）, `pages/help.py`（SC-03）
- `app.py`（エントリ、サイドバー radio で画面切替）
- `app.yaml`（Databricks Apps）, `README.md`, `.gitignore`

## 変更内容（方針）

- 役割分担（`.agents/rules/agent-orchestration.md`）に従い、ルーチン実装は
  `implementer-sonnet` に委譲、最難所の Pillow 合成 `compose_canvas` はメインが直接実装。
- 各実装ステップ完了ごとにメインが差分を監査してから次へ進む（無監査コミット禁止）。
- 依存順: data → map_builder → png_builder → zip_builder → pages → app。

## 検証方法

1. `venv/bin/pip install -r requirements.txt`、`gen_sample.py` で CSV 生成。
2. `lib/data.py` の絞込・連番・ズーム階段を単体確認。
3. `compose_canvas` をプレースホルダ地図で 1280×720 生成・目視（ヘッダー／カード／
   「他N件」／日本語フォント）。`build_png` 全経路（headless Chrome + OSM タイル）も試行。
4. `streamlit run app.py` の headless 起動スモークテスト（HTTP 200 / health 200）。
5. SPEC §12 受入条件を全項目突合。

## 記録方針

- 本 plan と対の result を `docs/history/` に保存し、`CHANGELOG.md` に1行追記する
  （`.agents/rules/plan-before-modify.md` §3/§4）。
