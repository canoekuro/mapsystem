"""
データ更新（アップロード）ページ。

推進園データ・店舗データ・RDPデータの Excel（.xlsx / .xls）をアップロードし、「更新」押下で
Unity Catalog Volume の所定フォルダへ格納する。各ファイルは固定のベース名（nursery / store /
rdp）＋アップロードされた拡張子（nursery.xlsx / rdp.xls など）に変換され、格納先フォルダ内の
同名（ベース名）ファイルを置き換える。削除は対象ベース名に限定するため、同一フォルダに複数
ベース名が同居しても互いを消さない。一部のみのアップロードにも対応し、その場合はその側の
ベース名のみ更新する。テーブルの更新は Databricks ジョブ側で実行される。

Public API
----------
render() -- render the upload page.
"""

import logging
import os

import streamlit as st

from lib.volume import load_volume_config, replace_in_volume

logger = logging.getLogger(__name__)

# Volume フォルダ未設定（プレースホルダのまま）を検知するためのデフォルト値。
_PLACEHOLDER_PREFIX = "/Volumes/catalog/schema/volume_name"

# アップロードを受け付ける拡張子（Excel）。
_ALLOWED_EXTS = ["xlsx", "xls"]

# (UI ラベル, 設定キー, 保存ベース名, file_uploader の key)
_TARGETS = [
    ("推進園データ（xlsx/xls）", "nursery_dir", "nursery", "up_nursery"),
    ("店舗データ（xlsx/xls）", "store_dir", "store", "up_store"),
    ("RDPデータ（xlsx/xls）", "rdp_dir", "rdp", "up_rdp"),
]


def _stored_filename(base: str, uploaded_name: str) -> str:
    """保存ファイル名を返す。アップロードされた拡張子を保持する（既定は .xlsx）。"""
    ext = os.path.splitext(uploaded_name)[1].lower().lstrip(".")
    if ext not in _ALLOWED_EXTS:
        ext = "xlsx"
    return f"{base}.{ext}"


def render() -> None:
    """Render the data-upload page."""
    st.header("データ更新")
    st.info(
        "Excelファイルをアップロードし「更新」を押すと ファイルがアップロードされ、データ更新が開始します。"
    )

    config = load_volume_config()

    # アップローダを横並びで配置。
    uploaded: dict[str, object] = {}
    cols = st.columns(len(_TARGETS))
    for col, (label, config_key, _base, widget_key) in zip(cols, _TARGETS):
        with col:
            uploaded[config_key] = st.file_uploader(label, type=_ALLOWED_EXTS, key=widget_key)

    has_any = any(uploaded[key] is not None for _, key, _, _ in _TARGETS)
    if st.button("更新", type="primary", disabled=not has_any):
        for label, config_key, base, _widget_key in _TARGETS:
            file = uploaded[config_key]
            if file is None:
                continue

            dir_path = config.get(config_key)
            if not dir_path:
                st.error(f"{label}: 格納先フォルダが未設定です（config の [volume] {config_key}）")
                continue
            if str(dir_path).startswith(_PLACEHOLDER_PREFIX):
                st.warning(
                    f"{label}: 格納先がプレースホルダ（{dir_path}）のままです。"
                    "config/databricks_config.toml の [volume] を実際の Volume パスに設定してください。"
                )

            try:
                filename = _stored_filename(base, file.name)
                path = replace_in_volume(dir_path, filename, base, file.getvalue())
                st.success(f"{label}: 格納しました → {path}")
            except Exception as e:  # noqa: BLE001
                logger.exception("アップロードに失敗しました: %s", label)
                st.error(f"{label}: アップロードに失敗しました: {e}")
