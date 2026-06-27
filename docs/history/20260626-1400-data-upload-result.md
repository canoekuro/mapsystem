# 結果: データアップロード機能の追加

- 日時: 2026-06-26 14:00
- テーマ: data-upload
- 対応する計画: [20260626-1400-data-upload-plan.md](20260626-1400-data-upload-plan.md)

## 変更内容

### `lib/volume.py`（新規）

- `load_volume_config()`: `config/databricks_config.toml` の `[volume]` を返す
  （FileNotFound 時は `{}`）。`lib/data.py` の tomllib パターンを踏襲。
- `replace_in_volume(dir_path, filename, data) -> str`: `WorkspaceClient` で
  `list_directory_contents` ＋ `delete` によりフォルダ内の既存ファイルを全削除（ディレクトリ
  未作成等の例外は INFO ログで無視）し、`files.upload(..., overwrite=True)` で固定名格納。
  保存先パスを返す。`WorkspaceClient` / `databricks.sdk` は関数内で遅延 import。

### `views/upload_page.py`（新規）

- `render()`: 説明（`st.info`）＋ `st.columns(2)` に xlsx 限定の `st.file_uploader` ×2
  （推進園 / 店舗）。「更新」ボタンは両方未選択時 `disabled`。
- 押下時、アップロードされた側のみ `replace_in_volume(dir, 固定名, file.getvalue())` を実行。
  推進園 -> `nursery.xlsx`、店舗 -> `store.xlsx`。成功は `st.success`（保存先パス）、失敗は
  `st.error` ＋ `logger.exception`。
- `[volume]` 設定が無い場合は `st.error`、プレースホルダ（`/Volumes/catalog/schema/volume_name`
  始まり）のままなら `st.warning` で注意喚起。

### `app.py`

- `st.navigation` / `st.Page` でマルチページ化。`マップ`（`_map_page`, default）と
  `データ更新`（`_upload_page`）。
- `_map_page` は `load_company_names()` の例外をページ内 `st.error` で表示して `return`
  （`st.stop()` を廃止）。これによりテーブル参照が失敗してもデータ更新ページは利用可能。

### `config/databricks_config.toml`

- `[volume]` セクションを追加。`nursery_dir` / `store_dir` をプレースホルダ
  （`/Volumes/catalog/schema/volume_name/...`）で定義。

### `requirements.txt`

- `databricks-sdk>=0.20` を追加（`WorkspaceClient` 用）。

## 検証結果

- 構文パース（`app.py` / `lib/volume.py` / `views/upload_page.py`）→ **OK**。
- `config/databricks_config.toml` の TOML ロード → **OK**。
- `import lib.volume` → **OK**（databricks.sdk は遅延 import のため未接続環境でも読込可）。
- `views.upload_page` / `app.py` の import は `streamlit` 未導入のため本環境では未実施
  （構文パスは確認済み。`st.navigation` / `st.Page` は streamlit>=1.36 で提供）。

## 未対応事項

- Databricks 実接続での手動検証（格納・既存削除・片側のみ更新・権限）は接続環境が必要なため
  未実施。
- `[volume]` のパスはプレースホルダのため、デプロイ前に実際の Volume パスへ差し替えが必要。
- アップロード・削除には Databricks Apps のサービスプリンシパルへ対象 Volume の
  `WRITE VOLUME` 権限付与が必要（範囲外）。
