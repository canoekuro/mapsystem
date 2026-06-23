"""
SC-03: ヘルプ画面

Public API
----------
render(df) -- render the page; df is accepted for interface consistency but
              not used (this page shows static content only).
"""

import streamlit as st


def render(df) -> None:
    """Render SC-03: help / data-source attribution page (SPEC §6.3)."""
    st.header("データ出典")

    st.markdown(
        "位置参照情報（大字町丁目・街区レベル）令和6年（国土交通省）、  \n"
        "電子国土基本図（地名情報）住居表示住所（国土地理院）、  \n"
        "Geolonia 住所データ（株式会社Geolonia）"
        " [https://geolonia.github.io/japanese-addresses/](https://geolonia.github.io/japanese-addresses/)、  \n"
        "アドレス・ベース・レジストリ（デジタル庁）  \n"
        "[https://www.digital.go.jp/policies/base_registry_address_tos/]"
        "(https://www.digital.go.jp/policies/base_registry_address_tos/)  \n"
        "登記所備付地図データ（法務省）  \n"
        "をもとに、株式会社情報試作室が加工した  \n"
        "jageocoder 用住所データベース（住居表示レベル）を利用",
        unsafe_allow_html=False,
    )
