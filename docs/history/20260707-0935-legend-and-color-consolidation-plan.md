# 計画: 色分け凡例の追加と色定義の共通化

- **日時:** 2026-07-07 09:35
- **対象 issue:** `docs/issues/推進園区分の色分け.md`（フォローアップ）
- **テーマ:** 推進園区分の凡例表示と、4箇所に重複していた色定義の一元化

## 1. 背景・目的

先行対応（20260707-0906）で `推進園区分` の実値による色分けを有効化した。ユーザー要望により
以下を追加する。

1. **凡例の追加** — 区分（認可保育所 / 認定こども園 / 幼稚園）と色の対応を地図上に表示。
2. **色定義の共通化** — `_FACILITY_COLORS` が `map_builder` / `png_builder` / `static_map` /
   `main_page` の4箇所に重複しており、今回のドリフト不具合の根本原因。単一の定義へ集約する。

## 2. 変更内容

### 共通モジュール `lib/colors.py`（新規）

- `FACILITY_COLORS`（区分→16進色、定義順=凡例順）、`FALLBACK_COLOR` を唯一の定義とする。
- ヘルパ: `facility_color(cat)`、`hex_to_rgb(hex)`、`facility_color_rgb(cat)`。

### 各モジュールの参照差し替え

| ファイル | 変更 |
|---|---|
| `lib/map_builder.py` | 重複定義を削除し `lib.colors` を参照。地図左下に HTML 凡例を重ねる |
| `lib/static_map.py` | 重複定義を削除し `facility_color_rgb` を参照。PNG に凡例を焼き込む |
| `lib/png_builder.py` | 重複定義を削除し `facility_color` を参照（凡例は地図PNGが保持） |
| `views/main_page.py` | ローカルの色定義/ヘルパを削除し `facility_color` を参照 |
| `SPEC.md` | §6.1.2 に色定義の一元化と凡例表示を明記 |

### 凡例の実装方針

- インタラクティブ地図（folium）: 絶対配置の HTML 断片を地図左下に重ねる。
- ダウンロード/静的PNG: `static_map` が地図画像左下に凡例を Pillow で描画。`png_builder` は
  その地図PNGを貼り込むため凡例は自動的に合成画像へ反映される（凡例描画を一箇所に集約）。

## 3. 検証方法

- `lib.colors` の値・RGB 変換・フォールバックを確認。
- タイル取得をモックして `static_map` / `png_builder` / `map_builder` を実描画し、
  凡例と各区分色が出ることを目視・文字列両面で確認。

## 4. 記録

- 本 plan / result を `docs/history/` に保存し、`CHANGELOG.md` に1行追記。
