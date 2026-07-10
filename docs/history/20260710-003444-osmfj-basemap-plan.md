# OSMFJ タイルをベースマップに追加（計画）

- 日付時刻: 2026-07-10 00:34:44
- テーマ: 地図スタイルへ OSMFJ（OpenStreetMap Foundation Japan）タイルを追加
- ブランチ: `claude/osm-map-style-qz7bxw`

## 目的

地図の背景（ベースマップ）の選択肢に、OSMFJ が配信する日本語スタイルの
ラスターXYZタイルを追加する。提供元グループは新設せず、既存の
`PROVIDER_OSM`（"OpenStreetMap"）にまとめて、設定ページの提供元一覧を増やさない。

## 背景

- 本システムのベースマップはラスターXYZタイルを差し込む方式（`lib/basemaps.py`）で、
  `BASEMAPS` 辞書へ1エントリ追加するだけで対話地図(folium)・PNG合成(static_map)の
  双方へ反映される。
- OSMFJ は `https://tile.openstreetmap.jp/{z}/{x}/{y}.png` で日本語ラベルに
  最適化された OSM 標準スタイルを配信しており、単一ホスト前提の本設計と合致する。

## 対象ファイルと変更内容

1. `lib/basemaps.py`
   - `BASEMAPS` の OSM グループ（`osm_hot` の直後）に `osmfj_japan` を追加。
   - `provider` は既存 `PROVIDER_OSM`、`label` = "日本語スタイル"、
     `url` = `https://tile.openstreetmap.jp/{z}/{x}/{y}.png`、
     `attribution` = `f"{_OSM_ATTR}, Tiles: OSMFJ"`、`max_zoom` = 18。
2. `config/theme.toml`
   - コメントの id 一覧を `#   OSM: osm_standard / osm_hot / osmfj_japan` に更新。
3. `docs/history/`
   - 本 plan と対の result を保存。
4. `CHANGELOG.md`
   - `[Unreleased]` の 2026-07-10 配下に1行追記＋詳細リンク。

## 検証方法

- `lib.basemaps` を import し、以下を確認:
  - `is_valid("osmfj_japan")` が真。
  - `basemaps_for_provider("OpenStreetMap")` に `osmfj_japan` が含まれる。
  - `providers()` が3件のまま（新グループが発生していない）。

## 留意点

- OSMFJ は日本コミュニティ運営サーバーのため、高負荷・商用運用時は利用規約の
  確認が必要。帰属表示は attribution に付与済み。
- 提供上限は概ね z18 のため `max_zoom` を 18 とする。
