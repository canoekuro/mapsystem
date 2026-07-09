"""
アプリのUI表示設定（config/app_config.toml）の読込ヘルパ。

画面に表示するページの出し分けなど、UIレベルの切替を一元管理する。値は
``config/app_config.toml`` の ``[ui]`` から読み込み、未存在・キー欠損・不正時は
安全側の既定へフォールバックする（lib/data.py の tomllib ローダと同型）。

Public API
----------
show_theme_page() -- 「テーマ設定」ページをナビゲーションに表示するか（既定 False）
"""

import tomllib

_APP_CONFIG_PATH = "config/app_config.toml"


def _load_ui_config() -> dict:
    """config/app_config.toml の [ui] を読む。未存在・不正時は空 dict。"""
    try:
        with open(_APP_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return {}
    return data.get("ui", {}) or {}


def show_theme_page() -> bool:
    """「テーマ設定」ページを表示するかを返す（未設定・非真偽値時は既定 False）。"""
    value = _load_ui_config().get("show_theme_page", False)
    return value is True
