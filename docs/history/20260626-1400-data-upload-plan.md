# 計画: データアップロード機能の追加

- 日時: 2026-06-26 14:00
- テーマ: data-upload

## 背景・目的

現在のアプリは Unity Catalog テーブルからの読み取り専用で、データを更新する手段が無い。
データの加工とテーブル更新自体は Databricks のジョブ側で行うため、アプリの責務は
「推進園データ・店舗データ（いずれも Excel）を受け取り、Unity Catalog Volume の所定
フォルダへ格納する」ことに限定する。ジョブはそのフォルダを参照して後続処理を行う。

要件:
- ファイルは Excel（xlsx）。中身の検証・加工は行わず、バイト列をそのまま格納する。
- 推進園・店舗で UI 上のアップロード場所も格納先 Volume フォルダも分ける。
- 保存名は固定変換: 推進園 -> `nursery.xlsx`、店舗 -> `store.xlsx`。
- 更新ボタン押下時、アップロードした側のフォルダ内の既存ファイルを削除してから格納する。
  片方のみアップロード時はその側のフォルダのみ更新し、もう片方は触らない。
- UI はマップ画面とは別ページ（マルチページ）に置く。
- 片方だけのアップロードにも対応する。

## 対象ファイル

- `lib/volume.py`（新規） — `replace_in_volume()`（既存削除 → 固定名アップロード）、
  `load_volume_config()`。
- `views/upload_page.py`（新規） — アップロード画面 `render()`。
- `app.py` — `st.navigation` / `st.Page` でマルチページ化。
- `config/databricks_config.toml` — `[volume]`（nursery_dir / store_dir）追加。
- `requirements.txt` — `databricks-sdk>=0.20` 追加。

## 変更内容

- `lib/volume.py`: `WorkspaceClient` で Volume を操作。`replace_in_volume(dir_path,
  filename, data)` はフォルダ内の既存ファイルを `list_directory_contents` ＋ `delete` で
  全削除（NotFound は無視）してから `files.upload(overwrite=True)` で固定名格納し、保存先
  パスを返す。フォルダが推進園・店舗で分離しているため、片方のみ呼べば「その側だけ削除」を
  満たす。
- `views/upload_page.py`: `st.file_uploader`（xlsx のみ）×2 を `st.columns(2)` で配置。
  「更新」ボタン（両方未選択時 `disabled`）押下で、アップロードされた側のみ
  `replace_in_volume()` を呼ぶ。成功は `st.success`（保存先パス表示）、失敗は `st.error`
  ＋ログ。`[volume]` がプレースホルダのままなら `st.warning`。
- `app.py`: `st.set_page_config` の後、`st.navigation([st.Page(マップ, default=True),
  st.Page(データ更新)]).run()`。マップページは `load_company_names()` 失敗時もアップロード
  ページが使えるよう、例外をページ内で `st.error` 表示し `st.stop()` は使わない。
- `config/databricks_config.toml`: `[volume] nursery_dir / store_dir` をプレースホルダで追加。
- `requirements.txt`: `databricks-sdk>=0.20`。

## 検証方法

- 新規・変更ファイルの構文パース、`config` の TOML ロード、`lib.volume` の import。
- `streamlit run app.py` でサイドバーに2ページが出ること、xlsx 以外を弾くこと、両方未選択で
  「更新」が `disabled` になることの確認（要 streamlit）。
- Databricks 実接続での格納・既存削除・片側のみ更新の確認（要接続）。
