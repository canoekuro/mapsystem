# 計画: pptx テキストプレースホルダーに小売店名称を挿入（issue 202607221450）

## 背景・目的

issue `docs/issues/202607221450.md`:

> template.pptx のテキストのプレースホルダーに、文章を入れたい。「選択した小売店名称」を入れるようにしたい。

商談用資料 / 店舗POP の pptx 生成（`lib/pptx_builder.py`）は、テンプレートの画像プレースホルダーへ
地図PNGを貼り付けるのみで、テキストプレースホルダー（`images/template.pptx` の
「テキスト プレースホルダー 2」/ `type=body` / `idx=12`）は空のままだった。
本変更で、このテキストプレースホルダーへ「選択中の小売店名称 + 定型文」を挿入する。

ユーザー確認により、入れる文言は **「店舗名 + 定型文」形式**、定型文（フォーマット）は
**config で指定**する方針に決定。

## 変更対象ファイルと内容

1. `config/databricks_config.toml` — `[pptx]` に `store_caption_format = "{store} 周辺マップ"` を追加
   （`{store}` が小売店名称に置換。商談用資料・店舗POP で共通）。
2. `lib/pptx_builder.py`
   - `load_caption(store)` を追加: config の `store_caption_format` に `store` を差し込む。
     `store` 空/None は空文字を返す。書式不正時は warning を出し店舗名のみ返す。
   - `_fill_text_placeholder(slide, text)` を追加: `insert_picture` を持たず `text_frame` を持つ
     最初のプレースホルダーへ書き込む（idx ハードコードせず型/能力ベースで検出。未検出は warning）。
   - `build_store_pptx(template_bytes, map_png_bytes, caption_text=None)` に拡張。
     `caption_text` が非空なら `_fill_text_placeholder` を呼ぶ。画像貼り付けとは別枠で干渉しない。
3. `views/main_page.py`
   - import に `load_caption` を追加。
   - キャッシュ関数 `_store_pptx(map_png, kind, store)` に `store` を追加し
     `build_store_pptx(load_template_bytes(kind), map_png, load_caption(store))` を返す
     （store をキャッシュキーに含める副次効果あり）。
   - download_button 2 箇所を `_store_pptx(map_png, "shoudan", store)` / `..., "pop", store)` に更新。

## 拡張ポイント（今回未実装）
種別ごとに定型文を変えたい場合は `shoudan_caption_format` / `pop_caption_format` を config に追加し、
`load_caption(store, kind)` で切り替える形へ拡張可能。

## 検証方法
- `python-pptx` / `Pillow` を導入し、`images/template.pptx` + 小PNG + caption で `build_store_pptx` を実行。
- 出力 pptx を unzip し `ppt/slides/slide1.xml` に caption 文字列が含まれ、かつ画像（`ppt/media/`・`<a:blip>`）
  が挿入されていることを確認。
- `load_caption("テスト店")` が config 定型文を反映、`load_caption(None/"")` が空文字であることを確認。
