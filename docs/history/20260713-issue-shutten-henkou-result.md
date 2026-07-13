# 結果: 地図の帰属表示（GSI 出典）を追記掲載向けの表記へ変更

- 日時: 2026-07-13
- テーマ: issue-出典変更
- 起点 issue: `docs/issues/出典変更.md`

## 背景

地理院タイル（GSI）にアプリ側で店舗・推進園のマーカー等を重ねて掲載しているため、
地理院タイルの利用規約が定める「地理院タイルに○○を追記して掲載」の表記に合わせる。
マップ上の出典を「国土地理院」の表記から
「地理院タイルに店舗・推進園情報を追記して掲載」へ変更する。

## 変更内容

### `lib/basemaps.py`
- GSI ベースマップの帰属表示定数を変更。
  - 変更前: `_GSI_ATTR = "出典: 国土地理院"`
  - 変更後: `_GSI_ATTR = "出典: 地理院タイルに店舗・推進園情報を追記して掲載"`
- この定数は `gsi_std` / `gsi_pale` / `gsi_photo` / `gsi_blank` の
  `attribution` に共有されており、4 スタイルすべてに反映される。
- 提供元グループ名 `PROVIDER_GSI`（設定ページの提供元選択の表示ラベル「国土地理院」）は
  変更しない。今回の対象はマップ上に焼き込まれる出典表記のみ。

## 反映箇所（コード変更なし・表示への波及）
- 対話地図（folium）: `lib/map_builder.py` が `attr=bm["attribution"]` として表示。
- ダウンロード PNG: `lib/static_map.py` の `_draw_attribution` が右下に焼き込み。
  帰属表示ボックスは右端起点で左方向に伸びる実装のため、文言が長くなっても
  右端からはみ出さない（既定サイズ 656px に対し余裕あり）。
- 設定ページの選択中背景キャプション: `views/config_page.py` が
  `bm['attribution']` を表示。

## 検証結果
- AST parse（`lib/basemaps.py`）→ **OK**。
- `get_basemap('gsi_std' / 'gsi_pale' / 'gsi_photo' / 'gsi_blank')['attribution']`
  が すべて `出典: 地理院タイルに店舗・推進園情報を追記して掲載` を返すことを確認。
- `providers()` は `['OpenStreetMap', '国土地理院', 'CARTO']` のまま（グループ構成に変化なし）。
