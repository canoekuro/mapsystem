# 計画: pptx キャプション定型文をテーマ設定ページで編集可能にする（issue 202607221450 フォローアップ）

## 背景・目的

issue 202607221450 の初回対応（PR #31）で pptx のテキスト枠へ「小売店名称 + 定型文」を挿入できるようにしたが、
定型文フォーマットは `config/databricks_config.toml` にハードコードされていた。
ユーザー要望「テーマ設定ページでデフォルト定型文を指定できるようにしたい」に対応する。

アプリが唯一書き込める設定ファイルは `config/theme.toml`（`lib/colors.save_theme()` が唯一のライター）で、
テーマ設定ページの保存／TOMLダウンロード／既定に戻す機構はすべて theme.toml 前提。
そこで定型文を **theme.toml へ移設**し、`lib/colors` のテーマ値として扱う。

## 変更対象ファイルと内容

1. `lib/colors.py`
   - `_DEFAULTS` に `store_caption_format = "{store} 周辺マップ"` を追加。
   - `_load_from_file()` に `[pptx]` セクションの読み取りを追加。
   - `_merge()` に文字列検証ブランチ（`isinstance(str) and value`）を追加。
   - アクセサ `store_caption_format()` を追加。
   - `theme_toml_text()` に `[pptx]` セクション出力を追加。TOML basic string の
     エスケープ用ヘルパー `_toml_basic_escape()`（`\`→`\\`, `"`→`\"`）を追加。
2. `config/theme.toml`: `[pptx] store_caption_format` セクションを追記。
3. `views/config_page.py`: `_CAPTION_KEY` を追加、`_init_state`/`_reset_to_default`/`_collect_values` に配線、
   `render()` に `st.text_input`（`{store}` 置換の説明 + 入力値の live プレビュー/書式検証）を追加。
4. `lib/pptx_builder.py`: `load_caption` を `colors.store_caption_format()` 参照に変更。
   `{store}` フォーマット + try/except（不正時は店舗名のみ返す）は維持。
5. `config/databricks_config.toml`: PR #31 で追加した `store_caption_format` を削除。

## 検証方法

- `colors.store_caption_format()` / `load_caption("テスト店")` / `load_caption(None)` の値確認。
- `theme_toml_text()` の出力に `[pptx]` があり `tomllib` で再パース可能、`"`・`\` を含む値のエスケープ往復。
- 書いた theme.toml を `_load_from_file()` で読み戻し値一致（round-trip）。
- 変更後テーマで `build_store_pptx(...)` を実行し `slide1.xml` にキャプションが入ることを確認。
- `ruff check`。
