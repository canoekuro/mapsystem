# result: 小売店テーブル分離 + マップpptx出力（issue 202607221128）

## 変更内容

### 要望1: 小売店テーブル分離
- `config/databricks_config.toml`: `[databricks] store_table` を追加（小売店マスタ。
  `企業名称/店舗名称/店舗コード/店舗_都道府県` の DISTINCT）。
- `lib/data.py`:
  - `_table_and_spark(key="table")` に引数追加（`store_table` も読めるように）。
  - `load_stores(company)` 新設: `store_table` を `企業名称==指定企業` のみで（距離条件なし）取得。
  - `store_nursery_counts(stores_df, nursery_df)` を2引数化: 小売店マスタに圏内推進園数を
    left join し `fillna(0).astype(int)`。圏内0件の店舗も `推進園数=0` で残る。
- `views/main_page.py`:
  - データ取得時に `load_filtered`（店舗×推進園）と `load_stores`（小売店マスタ）の両方を保存。
  - 取得件数サマリ・都道府県/小売店の選択肢を小売店マスタ（`stores_df`）から生成。
  - 小売店マスタが0件ならマップを描かず0件アラートで return。
  - 選択店舗が店舗×推進園DFに無い（圏内推進園0件）場合はマップ非表示で0件アラート。
  - 下部集計表を `store_nursery_counts(stores_df, df)` に差し替え。

### 要望2: マップpptx出力
- `requirements.txt`: `python-pptx>=0.6,<2` 追加（pure-Python、ブラウザ不要）。
- `config/databricks_config.toml`: `[pptx]`（`template_dir` / `shoudan_template` /
  `pop_template` / `local_fallback`）追加。
- `lib/pptx_builder.py`（新規）:
  - `load_template_bytes(kind)`: Volume からテンプレDL、失敗時 `images/template.pptx` へフォールバック。
  - `build_store_pptx(template_bytes, map_png)`: 1枚目スライドの画像プレースホルダーへ
    `insert_picture`。非対応テンプレは位置・サイズへ `add_picture` して元枠削除のフォールバック。
- `views/main_page.py`:
  - `データダウンロード` expander から都道府県 multiselect と画像ZIPボタンを撤去。CSVは企業全体。
  - 地図直下に「商談用資料ダウンロード」「店舗POPダウンロード」を配置。地図PNG（`_store_map_png`）は
    店舗ごとに1回生成し、両テンプレ（`_store_pptx`）で使い回す。

### ドキュメント
- `SPEC.md`: §4.1（小売店マスタ）、§6.1.2（pptxボタン）、§6.2（都道府県/画像廃止）、
  §7（F-04→pptx, F-08追加）、§8.4（ZIP廃止）、§8.5（pptx生成）、§9（pptx_builder.py）を更新。
- `CHANGELOG.md` の `## [Unreleased]` に追記。

## 検証結果
- スタンドアロン検証スクリプトで以下を確認（`python-pptx` インストール後）:
  - `store_nursery_counts`: S1=2, S2=1, **S3=0**（圏内0件の店舗が0で残存）。空 stores_df は空表。
  - `build_store_pptx`: 出力pptx `slides=1`, スライド0に `<p:pic>` 1件, メディアパーツ1件。
  - `load_template_bytes('shoudan'/'pop')`: Volume失敗→`images/template.pptx` フォールバック成功。
    未知kindは `ValueError`。
- `python -m py_compile` で `views/main_page.py` / `lib/data.py` / `lib/pptx_builder.py` OK。

## 未対応・留意
- 実地図タイル取得（`render_static_map`）は本環境のプロキシで遮断されるため、pptx検証は合成PNGで実施。
  貼り付け経路は同一（PNGバイト列）のため挿入ロジックの妥当性は担保される。
- 実テンプレ `to_shoudan.pptx` / `to_pop.pptx` は Databricks 上でのみ確認可能。`images/template.pptx`
  （clipArt idx=10）基準で実装し、`add_picture` フォールバックで構成差異を吸収する。
- `lib/png_builder.py` / `lib/zip_builder.py` は未使用だが当面残置。
