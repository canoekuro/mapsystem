# 結果: pptx テキストプレースホルダーに小売店名称を挿入（issue 202607221450）

対応する計画: [plan](20260722-071920-issue-pptx-store-caption-plan.md)

## 変更内容

- `config/databricks_config.toml`
  - `[pptx]` に `store_caption_format = "{store} 周辺マップ"` を追加。`{store}` が選択中の小売店名称に置換される。
- `lib/pptx_builder.py`
  - `load_caption(store)` を追加。config の `store_caption_format`（既定 `"{store}"`）に `store` を差し込む。
    `store` が空/None なら空文字、書式不正時は warning を出して店舗名のみを返す。
  - `_fill_text_placeholder(slide, text)` を追加。`insert_picture` を持たず `text_frame` を持つ最初の
    プレースホルダーへ `text` を書き込む（idx をハードコードせず型/能力ベースで検出。未検出は warning でスキップ）。
  - `build_store_pptx(template_bytes, map_png_bytes, caption_text=None)` に第3引数を追加。
    `caption_text` が非空のとき `_fill_text_placeholder` を呼ぶ。画像プレースホルダーとは別枠のため
    地図PNG貼り付けと干渉しない。docstring も更新。
- `views/main_page.py`
  - import に `load_caption` を追加。
  - キャッシュ関数を `_store_pptx(map_png, kind, store)` に変更し
    `build_store_pptx(load_template_bytes(kind), map_png, load_caption(store))` を返すよう修正。
    `store` がキャッシュキーに含まれ、同一PNG+kindでも店舗が変われば別デッキになる（従来の取り違えも解消）。
  - 商談用資料・店舗POP の download_button 2 箇所を `store` を渡す形に更新。

## 検証結果

`python-pptx==1.0.2` / `Pillow` を導入しスモークテストを実施（`images/template.pptx` を使用）:

- `load_caption("テスト店")` → `"テスト店 周辺マップ"`（config 定型文を反映）。
- `load_caption(None)` / `load_caption("")` → `""`（テキスト挿入なし）。
- `build_store_pptx(template, png, "テスト店 周辺マップ")` の出力 pptx を unzip:
  - `ppt/slides/slide1.xml` に `テスト店 周辺マップ` が含まれる（テキストプレースホルダーへ挿入成功）。
  - `ppt/media/image1.png` が存在し `<a:blip>`（picture）を確認（地図画像の貼り付けと共存）。

## 未対応事項 / 備考

- Databricks Volume の実テンプレ `to_shoudan.pptx` / `to_pop.pptx` はリポジトリ外のため未検証。
  テキストプレースホルダー検出は idx 非依存（型/能力ベース）にしてあり、テキスト枠を持つテンプレなら動作する。
  テキストプレースホルダーが存在しない場合は warning を出してスキップ（画像貼り付けは従来どおり）。
- 種別ごとの定型文差し替えは未実装（計画の拡張ポイント参照）。
- 定型文のデフォルト `"{store} 周辺マップ"` は仮置き。実文言は config で編集可能。
