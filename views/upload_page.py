"""
データ更新（アップロード）ページ。

推進園データ・店舗データの Excel をアップロードし、「更新」押下で Unity Catalog Volume の
所定フォルダへ格納する。各ファイルは固定名（nursery.xlsx / store.xlsx）に変換され、格納先
フォルダ内の既存ファイルを置き換える。片方のみのアップロードにも対応し、その場合はその側の
フォルダのみ更新する。テーブルの更新は Databricks ジョブ側で実行される。

Public API
----------
render() -- render the upload page.
"""

import logging

import streamlit as st

from lib.volume import load_volume_config, replace_in_volume

logger = logging.getLogger(__name__)

# Volume フォルダ未設定（プレースホルダのまま）を検知するためのデフォルト値。
_PLACEHOLDER_PREFIX = "/Volumes/catalog/schema/volume_name"

# (UI ラベル, 設定キー, 保存ファイル名, file_uploader の key)
_TARGETS = [
    ("推進園データ（xlsx）", "nursery_dir", "nursery.xlsx", "up_nursery"),
    ("店舗データ（xlsx）", "store_dir", "store.xlsx", "up_store"),
]


def render() -> None:
    """Render the data-upload page."""
    st.header("データ更新")
    st.info(
        "推進園・店舗の Excel をアップロードし「更新」を押すと Volume に格納されます"
        "（既存ファイルは置き換え）。片方のみのアップロードも可能です。"
        "テーブルの更新は Databricks ジョブ側で実行されます。"
    )

    config = load_volume_config()

    # アップローダを横並びで配置。
    uploaded: dict[str, object] = {}
    cols = st.columns(len(_TARGETS))
    for col, (label, config_key, _filename, widget_key) in zip(cols, _TARGETS):
        with col:
            uploaded[config_key] = st.file_uploader(label, type=["xlsx"], key=widget_key)

    has_any = any(uploaded[key] is not None for _, key, _, _ in _TARGETS)
    if st.button("更新", type="primary", disabled=not has_any):
        for label, config_key, filename, _widget_key in _TARGETS:
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
                path = replace_in_volume(dir_path, filename, file.getvalue())
                st.success(f"{label}: 格納しました → {path}")
            except Exception as e:  # noqa: BLE001
                logger.exception("アップロードに失敗しました: %s", label)
                st.error(f"{label}: アップロードに失敗しました: {e}")
