# 計画: Databricks データのオンデマンド取得（取得半径／表示半径の分離）

- 日時: 2026-06-26 05:00
- テーマ: on-demand-fetch

## 目的・背景

現状は `app.py` 起動時に `load_master()` で Databricks テーブルの全件（約5万行）を
`toPandas()` で取得し `@st.cache_data` にキャッシュしていた。データ増加に伴い起動が重く、
不要な転送が発生する。

要件:
1. 起動時は全件取得しない。企業名称の選択肢だけを軽量クエリで取得する。
2. 企業名称と取得半径の両方を指定して「データ取得」ボタンを押下したとき、その条件で
   Databricks 側を絞り込んで取得する。両方そろわなければボタンは無効。
3. 別条件で再押下すると新条件で再取得する。
4. 取得後に表示半径を取得半径以下で変更できる（例: 5km で取得して 2km で表示）ため、
   取得用半径と表示用半径を分離する。

## 対象ファイル

| ファイル | 変更内容 |
|---|---|
| `lib/data.py` | `load_master()` を削除。`_table_and_spark()` / `_rename_to_app_columns()` ヘルパー、`load_company_names()`（DISTINCT 軽量クエリ）、`load_filtered(company, fetch_radius_km)`（Spark 側フィルタ）を追加 |
| `app.py` | 起動時に `load_company_names()` のみ実行し `main_page.render(companies)` を呼ぶ |
| `views/main_page.py` | `render(companies)` に変更。取得行（企業＋取得半径＋データ取得ボタン）と表示行（小売店＋表示半径）に再構成。`st.session_state` に取得済み DF・条件を保持。`_company_image_zip` を取得済み DF 引数受け取り方式へ変更（`hash_funcs` で DF をキャッシュキーから除外） |
| `SPEC.md` / `README.md` / `CHANGELOG.md` | オンデマンド取得フローへ記述更新 |

## 設計の要点

- `load_filtered(company, fetch_radius)` は「その企業・距離km <= 取得半径の全行（全店舗・全列）」を返す。
  これ1つで地図表示・施設リスト・企業一括CSV・画像ZIP すべてを賄える。
- `@st.cache_data` のキーは `(company, fetch_radius_km)`。同一条件はキャッシュヒット、条件変更で再クエリ。
- 表示半径は `max_value=loaded_fetch_radius` で取得半径以下に制限し、取得範囲外の表示による欠落を防ぐ。
- 既存の純粋関数（`filter_facilities`, `filter_company`, `stores_for_company` 等）は取得済み部分集合に
  対してそのまま再利用する。

## 検証方法

1. `python -m py_compile lib/data.py views/main_page.py app.py`
2. `grep load_master`（残存参照ゼロ確認）
3. 純粋関数の回帰テスト（ダミー DF）: `filter_facilities` が表示半径で絞れること等
4. `load_filtered` / `load_company_names` のロジックをモック Spark で検証
   （企業＝指定 AND 距離km <= 取得半径 で除外が効くこと）
