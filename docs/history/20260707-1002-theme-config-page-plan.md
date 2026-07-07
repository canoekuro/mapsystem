# 計画: テーマ設定ページで配色を config から調整可能にする

- **日時:** 2026-07-07 10:02
- **テーマ:** 凡例・半径円・見出し帯・店舗マーカーの配色を設定ページ（config）で調整

## 1. 背景・目的

推進園区分の色は `lib/colors.py` に一元化済みだが、アクセント色（半径円・見出し帯・
施設リストヘッダー・店舗マーカー）は `#7C3AED` などがコード内4箇所にハードコードされていた。
これらを **設定ページから調整** できるようにする（保存先は config ファイル）。

## 2. 変更内容

### 新規
- `config/theme.toml`: `[theme]`（scalar 色/透明度）＋ `[theme.facility_colors]`。source of truth。
- `views/config_page.py`: 色ピッカー＋透明度スライダ＋プレビュー＋保存/DL/既定に戻す。
- `docs/history/` plan/result。

### `lib/colors.py` をテーマモジュールへ拡張
- `_DEFAULTS` と `get_theme()`（既定←ファイル←プロセス内オーバーライド、キャッシュ）。
- **描画時解決**のアクセサ: `facility_colors/facility_color(_rgb)`, `circle_color(_rgb)`,
  `circle_fill_opacity`, `band_color(_rgb)`, `store_marker_color(_rgb)`, `hex_to_rgb`。
- `apply_overrides` / `reload_theme` / `save_theme`（TOML 手組み書込）/ `theme_toml_text`。

### 描画側のハードコード撤去（テーマ参照へ）
- `map_builder`: 円色/透明度、凡例、店舗マーカーを **BeautifyIcon**（hex 指定可）へ。
- `static_map`: 円色(RGB)/alpha、店舗色(RGB)、凡例。
- `png_builder`: 見出し帯を `band_color()`。
- `main_page`: 見出し・リスト帯を `band_color()`。

### ナビ/ドキュメント
- `app.py`: `st.Page(テーマ設定)` を追加。
- `SPEC.md`: §6.1.2/§6.4/§8.3/§9 を更新（テーマ調整可・BeautifyIcon 化・ファイル構成）。
- `CHANGELOG.md` 追記。

## 3. 検証方法
- テーマ往復（save→file→get_theme 反映、facility 保持、hex 変換）。
- タイルモックで static/PNG/folium を実描画し、既定＝現状維持／オーバーライドで
  円・帯・店舗・マーカー・凡例色が変わることを確認。
- streamlit スタブで config_page.render と app ナビ登録を確認。

## 4. 未対応・申し送り
- Databricks Apps は FS 揮発性のため、ページ保存の恒久化は DL→リポコミットが必要（UI で誘導）。
- 保存はプロセス内共有のため、同一アプリインスタンスの全ユーザーへ即時反映される。
