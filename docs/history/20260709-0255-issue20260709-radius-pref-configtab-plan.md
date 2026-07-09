# 計画: 表示半径廃止・都道府県絞り込み追加・テーマ設定タブ表示制御

- 日付: 2026-07-09
- 対象 issue: `docs/issues/20260709.md`

## 目的・背景

`docs/issues/20260709.md` の3要望に対応し、単一ページ画面の半径・絞り込みUIを整理し、
テーマ設定タブの表示を config で制御できるようにする。

1. 表示半径の設定を廃止し、取得半径＝表示半径にする。
2. データの絞り込みに都道府県を追加し、順序を
   `企業名称 → 取得半径 →（データ取得）→ 都道府県 → 小売店名称` にする。
   UIは「都道府県」と「小売店名称」を横並び。
3. config で「テーマ設定」タブの表示・非表示を切り替える（デフォルト非表示）。

## 対象ファイルと変更内容

### アプリケーションコード
- `views/main_page.py`
  - 表示半径 `st.number_input` を撤去。`display_radius` 参照（ヘッダー・`st.metric`・
    `filter_facilities`・`build_map`・`st_folium` の key）を `loaded_fetch_radius` へ置換。
  - 表示行を `st.columns([1, 2])` にし、左に都道府県（単一選択・任意・index=None）、
    右に小売店名称を配置。都道府県選択時は `stores_for_company_prefectures`、未選択時は
    `stores_for_company` で小売店候補を切替（既存ヘルパを再利用）。
- `app.py`
  - `lib.app_config.show_theme_page()` が True のときだけ「テーマ設定」ページを
    `st.navigation` に登録する。

### 新規 config / ローダ
- `config/app_config.toml`（新規）: `[ui] show_theme_page = false`。
- `lib/app_config.py`（新規）: `tomllib` で `[ui]` を読む `show_theme_page() -> bool`。
  ファイル/キー欠損・非真偽値時は `False`。

### ドキュメント
- `SPEC.md`: §5.1 / §6.1.1（取得行・表示行の2段構成、都道府県追加）/ §8.2（取得半径＝表示半径、
  都道府県での店舗絞込）/ §6.4（テーマ設定タブの表示制御）/ §9（`config/app_config.toml`・
  `lib/app_config.py` を追加）。
- `docs/history/`: 本 plan と対の result。
- `CHANGELOG.md`: `## [Unreleased]` の `### 2026-07-09` に3件追記。

## 再利用する既存資産
- `lib/data.py`: `prefectures_for_company` / `stores_for_company_prefectures` /
  `stores_for_company` / `filter_facilities`。
- `lib/data.py` の tomllib ローダ（`_load_*_config`）と同型で `lib/app_config.py` を実装。

## 検証方法
- 構文チェック（`ast.parse`）。
- `lib/app_config.show_theme_page()` の単体確認: 既定 false、`true` 設定で True、
  ファイル削除・キー欠損で False。
- `display_radius` の残存が無いこと（コメントを除く）。
- 回帰: データダウンロード expander（別の都道府県 multiselect・CSV/ZIP）が従来通り。

## 影響・非互換
- 表示半径機能の廃止（取得半径で常に表示）。SPEC §8.2 の二段絞り込み仕様を改訂。
- テーマ設定タブが既定で非表示になる（`show_theme_page = true` で表示）。
