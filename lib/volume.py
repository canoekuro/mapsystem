"""
Unity Catalog Volume への書き込みヘルパー。

データアップロード機能（views/upload_page.py）から呼ばれ、アップロードされた Excel を
所定の Volume フォルダへ格納する。テーブルの更新は Databricks ジョブ側の責務であり、
本モジュールはファイルの差し替え（既存削除 → 固定名アップロード）までを担う。

Databricks Apps 上では WorkspaceClient() が自動的にクレデンシャルを取得する
（lib/data.py の DatabricksSession と同じ思想）。ローカル開発時は ~/.databrickscfg
または環境変数（DATABRICKS_HOST / DATABRICKS_TOKEN）を使用する。

Functions
---------
load_volume_config()  -- config/databricks_config.toml の [volume] セクションを返す
replace_in_volume()   -- フォルダ内の同名（ベース名）ファイルを削除してから固定名でアップロード
"""

import io
import logging
import os
import tomllib

logger = logging.getLogger(__name__)

_VOLUME_CONFIG_PATH = "config/databricks_config.toml"


def load_volume_config() -> dict:
    """Load the [volume] section from config/databricks_config.toml."""
    try:
        with open(_VOLUME_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("volume", {})
    except FileNotFoundError:
        return {}


def replace_in_volume(dir_path: str, filename: str, base: str, data: bytes) -> str:
    """
    Delete existing ``{base}.*`` files in *dir_path*, then upload *data* as *filename*.

    Returns the full path the file was stored at.  The deletion is scoped to the
    target base name (e.g. ``rdp.xlsx`` / ``rdp.xls``), so multiple upload targets
    (推進園 / 店舗 / RDP) can share the same folder without wiping each other —
    uploading one base name leaves the other bases' files untouched.  A missing
    folder (NotFound on listing) is ignored — the upload below creates it.
    """
    from databricks.sdk import WorkspaceClient  # noqa: PLC0415

    w = WorkspaceClient()

    # 既存ファイルの削除は対象ベース名（{base}.拡張子）に一致するものだけに限定する。
    # 同一フォルダに複数ベース名（nursery / store / rdp）が同居しても互いを消さない。
    # ディレクトリ未作成等は無視してアップロードへ進む。
    prefix = f"{base}."
    try:
        for entry in w.files.list_directory_contents(dir_path):
            if getattr(entry, "is_directory", False):
                continue
            if os.path.basename(entry.path).startswith(prefix):
                w.files.delete(entry.path)
                logger.info("削除しました: %s", entry.path)
    except Exception as e:  # noqa: BLE001
        logger.info("既存ファイルの一覧/削除をスキップ（%s）: %s", dir_path, e)

    path = f"{dir_path.rstrip('/')}/{filename}"
    w.files.upload(path, io.BytesIO(data), overwrite=True)
    logger.info("格納しました: %s", path)
    return path
