# plan: 小売店テーブル分離 + マップpptx出力（issue 202607221128）

## 背景・目的

`docs/issues/202607221128.md` の2要望に対応する。

1. **小売店の消失問題**: `load_filtered` が `距離km <= 取得半径` で店舗×推進園結合テーブルを
   絞るため、取得半径圏内に推進園が0件の店舗は行ごと消え、選択肢にも下部集計表にも出てこない。
   → 小売店マスタを別テーブル（`store_table`）として取得し、選択肢・集計表の土台を小売店マスタへ移す。
   推進園数は圏内データを left join して 0 埋めする。小売店が0件ならマップを出さず0件アラート。
2. **画像出力のpptx化**: 「画像をダウンロード」（都道府県選択→店舗別PNGのZIP）を廃止し、
   PowerPointテンプレートの画像プレースホルダーに地図画像を貼った pptx を出力。ボタンは
   「商談用資料ダウンロード」「店舗POPダウンロード」の2つ。都道府県選択は完全撤去。

### ユーザー確定事項
- pptx対象: 現在選択中の1店舗のみ（1スライド）
- 貼付画像: 地図のみ（`render_static_map` の出力）
- 小売店テーブル: 新規物理テーブルを参照（config に `store_table` キー追加）
- 都道府県撤去: expander から完全撤去（CSVも企業全体対象）

## 対象ファイル
- `config/databricks_config.toml`: `[databricks] store_table` と `[pptx]` セクション追加
- `lib/data.py`: `load_stores(company)` 追加、`store_nursery_counts` を2引数 left join 化、
  `_table_and_spark(key=...)` 化
- `lib/pptx_builder.py`（新規）: `load_template_bytes(kind)` / `build_store_pptx(template, png)`
- `views/main_page.py`: 両DF取得・選択肢土台を小売店マスタへ・0件アラート・都道府県撤去・
  pptx2ボタン（地図PNGを両テンプレで使い回し）
- `requirements.txt`: `python-pptx>=0.6,<2`
- `SPEC.md` §4.1/§6.1.2/§6.2/§7/§8.4-8.5/§9 更新
- `CHANGELOG.md` / 本 plan・result

## 検証方法
1. `store_nursery_counts(stores_df, nursery_df)` を合成データで呼び、圏内に無い店舗が
   `推進園数=0` で残ることを確認。空 stores_df は空表。
2. `build_store_pptx(images/template.pptx, 合成PNG)` を実行し、出力pptxが1スライドかつ
   画像プレースホルダー位置に `<p:pic>` が挿入され、メディアパーツが1つ増えることを確認。
3. `load_template_bytes` が Volume 失敗時に `images/template.pptx` へフォールバックすることを確認。
