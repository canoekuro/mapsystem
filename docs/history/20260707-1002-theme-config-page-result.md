# 結果: テーマ設定ページで配色を config から調整可能にする

- **日時:** 2026-07-07 10:02
- **対応 plan:** `docs/history/20260707-1002-theme-config-page-plan.md`

## 1. 変更内容

| ファイル | 変更 |
|---|---|
| `config/theme.toml`（新規） | `[theme]`＋`[theme.facility_colors]`。配色の source of truth |
| `lib/colors.py` | テーマモジュールへ拡張。`get_theme`/`save_theme`/`apply_overrides`/`reload_theme`/`theme_toml_text` と描画時解決アクセサ（facility/circle/band/store）を提供 |
| `lib/map_builder.py` | 円色・透明度・凡例をテーマ参照。店舗マーカーを `BeautifyIcon`（hex 指定可）へ変更 |
| `lib/static_map.py` | 円色(RGB)・alpha・店舗色(RGB)・凡例をテーマ参照 |
| `lib/png_builder.py` | 見出し帯・リスト帯を `band_color()` |
| `views/main_page.py` | 見出し帯・施設リストヘッダーを `band_color()` |
| `views/config_page.py`（新規） | 色ピッカー＋透明度スライダ＋プレビュー＋保存/TOML DL/既定に戻す |
| `app.py` | `st.Page(テーマ設定)` を追加 |
| `SPEC.md` | §6.1.2/§6.4/§8.3/§9 を更新 |

調整対象: 推進園区分3色＋フォールバック、半径円（線色＋塗り透明度）、見出し帯・施設リスト
ヘッダー、店舗マーカー色。テーマは描画時に解決するため、保存後は地図とダウンロードPNGの
双方へ反映される。

## 2. 検証結果

- **テーマ往復**: `save_theme` で `config/theme.toml` に書き込み→`get_theme` が反映値を返す
  （`circle_color` を変更して確認）。facility_colors は保持。`hex_to_rgb` 変換一致。テスト後は
  ファイルを既定へ復元済み。
- **描画反映**（タイルモック、ネット不要）:
  - 既定テーマ: 合成PNG が現状（青/橙/紫マーカー・紫帯・紫円・濃色店舗）と一致（回帰なし）。
  - オーバーライド（円=水色/帯=ピンク/店舗=橙/透明度0.20/facility 差替）: 円・帯・店舗・
    マーカー・凡例のすべてが変化することを合成PNGで目視確認。
  - `map_builder.build_map` の render HTML に円色・facility 色（既定/上書きとも）が含まれることを確認。
- **設定ページ/ナビ**: streamlit スタブで `config_page.render()` が例外なく動作し、プレビュー
  HTML に全テーマ色が含まれることを確認。`app.py` のナビに「テーマ設定」が登録される。

## 3. 未対応事項

- Databricks Apps 実機での目視は環境上不可（ロジックはモックで実描画確認済み）。
- ページ保存はプロセス内共有のため同一インスタンスの全ユーザーに即時反映。恒久化は
  「設定TOMLをダウンロード」→リポジトリへコミットが必要（UI で誘導済み）。
- `_FACILITY_COLORS` 由来の重複は解消済み。アクセント色の重複（旧 `#7C3AED` ×4）も撤去。
