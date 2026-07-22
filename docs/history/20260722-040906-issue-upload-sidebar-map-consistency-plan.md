# plan: アップロード拡張・DLボタンのsidebar化・企業名称のstore_table化・map/pptx体裁一致（issue 202607221245）

## 背景・目的

PR #28（issue 202607221128）は main にマージ済み。続く issue `docs/issues/202607221245.md` の
4要望に対応する。指定ブランチ `claude/docs-issue-202607221128-owdgs3` を origin/main から作り直し
（同名）、新規PRとして起票する。

## 要望と対応
1. **アップロードで .xls 対応**: `views/upload_page.py` の `file_uploader(type=["xlsx","xls"])`、
   保存名は拡張子保持（`_stored_filename`）。
2. **DLボタンを sidebar へ / expander 廃止**: ローデータ／店舗別推進園数／商談用資料／店舗POP の
   4ボタンを `st.sidebar` に集約（`views/main_page._render_sidebar_downloads`）。商談用/POP は
   選択中1店舗が対象で未選択・圏内0件時 `disabled`。
3. **企業名称を store_table から取得**: `lib/data.load_company_names` を `_table_and_spark(key="store_table")` へ。
4. **map/pptx体裁一致**: `lib/static_map.render_static_map` を width×height 対応に一般化し、
   `map_width×map_height`・viewport=縦(height) で生成。`lib/pptx_builder.build_store_pptx` を
   アスペクト保持の `add_picture` 主体へ変更（`insert_picture` のクロップ回避）。

## 対象ファイル
- `views/upload_page.py` / `views/main_page.py` / `lib/data.py` / `lib/static_map.py` /
  `lib/pptx_builder.py` / `SPEC.md` / `CHANGELOG.md` / `docs/history/*`

## 検証
- `_stored_filename` が拡張子保持（xlsx/XLS/想定外→xlsx）。
- `render_static_map(width=700,height=560)` が 700×560、既定は 656×656。
- `build_store_pptx` がアスペクト比 1.25 を保って1スライドに `<p:pic>` 貼付。
- `py_compile` 全ファイル。`streamlit run` で sidebar4ボタン・expander非表示を目視。
