# 結果: 色分け凡例の追加と色定義の共通化

- **日時:** 2026-07-07 09:35
- **対応 plan:** `docs/history/20260707-0935-legend-and-color-consolidation-plan.md`

## 1. 変更内容

計画どおり実装した。

| ファイル | 変更 |
|---|---|
| `lib/colors.py`（新規） | `FACILITY_COLORS` / `FALLBACK_COLOR` と `facility_color` / `hex_to_rgb` / `facility_color_rgb` を唯一の定義として集約 |
| `lib/map_builder.py` | 重複定義を削除し `lib.colors` を参照。`_legend_html()` を追加し地図左下に凡例を重ねる |
| `lib/static_map.py` | 重複定義を削除し `facility_color_rgb` を参照。`_draw_legend()` を追加し地図PNG左下に凡例を焼き込む |
| `lib/png_builder.py` | 重複定義を削除し `facility_color` を参照 |
| `views/main_page.py` | ローカルの `_FACILITY_COLORS` / `_FALLBACK_COLOR` / `_facility_color` を削除し `facility_color` を参照 |
| `SPEC.md` | §6.1.2 に「色定義は `lib/colors.py` に一元化」「地図左下に凡例を表示」を明記 |

`_FACILITY_COLORS` の重複はゼロになり、色定義の変更は `lib/colors.py` 一箇所で全描画に反映される。

## 2. 検証結果

- `lib.colors`: `FACILITY_COLORS` 3区分、`FALLBACK_COLOR=#6B7280`、`facility_color_rgb("認可保育所")=(34,197,94)`、未知値→`(107,114,128)` を確認。
- タイル取得をモックして実描画:
  - `static_map.render_static_map` → 凡例付き地図PNGを生成（左下に「推進園区分」＋3区分の色見本）。
  - `png_builder.compose_canvas` → 合成PNGに地図の凡例・マーカー色・施設リストのバッジ色が反映されることを目視確認。
  - `map_builder.build_map` → レンダリングHTMLに3区分名と凡例タイトル「推進園区分」が含まれることを確認。
- 重複定義の残存が無いこと（`_FACILITY_COLORS` はソースから消滅、参照は4モジュールとも `lib.colors`）を grep で確認。

## 3. 未対応事項

- Databricks Apps 実機上での目視確認は本環境では不可（streamlit/selenium 非導入）。ロジックは
  タイルモックで実描画確認済み。
- folium 凡例は iframe 内で絶対配置（左下）。極端に小さいビューポートでの重なりは未検証。
