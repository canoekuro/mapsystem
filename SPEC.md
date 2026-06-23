# マップアプリ 実装仕様書 v1.0

## 1. 概要

担当小売店周辺の施設を可視化し、流通・個店提案に活用するためのWebアプリケーション。

## 2. 提供形態・実行環境

| 項目 | 内容 |
|---|---|
| デプロイ先 | Databricks Apps |
| 言語 | Python 3.11 |
| UIフレームワーク | Streamlit |
| 想定ブラウザ | Microsoft Edge / Google Chrome（最新版） |
| 起動エントリ | `app.py` |

## 3. 技術スタック

| 用途 | ライブラリ | バージョン目安 |
|---|---|---|
| UI | streamlit | 1.36 以上 |
| データ処理 | pandas | 2.x |
| 地図描画 | folium | 0.16 以上 |
| Streamlit-Folium連携 | streamlit-folium | 0.20 以上 |
| 番号付きマーカー | folium.plugins.BeautifyIcon | folium付属 |
| 地図のPNG化 | selenium 経由（`folium.Map._to_png`） | selenium 4.x |
| 画像合成 | Pillow | 10.x |
| ヘッドレスブラウザ | Chromium + chromedriver | Databricks Apps の `app.yaml` でインストール |
| ZIP生成 | 標準ライブラリ `zipfile` / `io.BytesIO` | - |

`requirements.txt` に上記Pythonライブラリを明記すること。Chromiumは`app.yaml`でOSパッケージとしてインストールすること。

## 4. 入力データ仕様

### 4.1 ファイル

- パス: `data/master.csv`
- 文字コード: UTF-8 (BOM無)
- 区切り: カンマ
- 想定件数: 約 5万行（店舗 × 推進園 の組合せ）

### 4.2 カラム定義

| カラム名 | 型 | 必須 | 説明 |
|---|---|---|---|
| 企業名称 | str | ○ | 例: ヨークベニマル |
| 業態名称 | str | ○ | 例: GMS |
| 小売店コード | str | ○ | 店舗一意キー |
| 小売店名称 | str | ○ | 例: アピタ千代田橋店 |
| 店舗住所 | str | ○ | 表示用 |
| 店舗緯度 | float | ○ | WGS84 |
| 店舗経度 | float | ○ | WGS84 |
| 施設名称 | str | ○ | 推進園名 |
| 施設区分 | str | ○ | `保育園` / `幼稚園` / `こども園` のいずれか |
| 施設住所 | str | ○ | 表示用 |
| 施設緯度 | float | ○ | WGS84 |
| 施設経度 | float | ○ | WGS84 |
| 距離 | float | ○ | km、小数第1位まで、事前算出済み |

### 4.3 前提

- 距離は事前計算済みのため、アプリ内で再計算しない
- 1店舗に対し複数行（施設数ぶん）存在する
- 距離による重複除外は行わず、そのまま件数化する

## 5. 画面構成

### 5.1 画面一覧

| ID | 画面名 | サイドバーナビゲーション表示名 |
|---|---|---|
| SC-01 | マップ画面（個別） | 店舗周辺マップ |
| SC-02 | マップ画面（企業一括） | 企業一括出力 |
| SC-03 | ヘルプ画面 | ヘルプ |

`st.sidebar.radio` で画面切替を行う。

## 6. 画面詳細

### 6.1 SC-01 マップ画面（個別）

#### 6.1.1 サイドバー（左ペイン）

上から順に以下を配置:

1. アプリタイトル `店舗周辺マップ`（`st.sidebar.title`）
2. ナビゲーション `st.sidebar.radio`（SC-01/02/03）
3. 区切り線 `st.sidebar.divider()`
4. 入力フォーム
   - 小売店名称: `st.sidebar.selectbox`
     - 選択肢は `master.csv` の `小売店名称` のユニーク値を昇順
     - プレースホルダ `店舗を選択してください`
   - 半径(km): `st.sidebar.number_input`
     - `min_value=0.1`, `max_value=50.0`, `value=2.0`, `step=0.1`
     - ラベル `半径(km)`
5. 実行ボタン: `st.sidebar.button("表示")`

#### 6.1.2 メインエリア レイアウト

Streamlit カラム比率: `st.columns([2, 1])` で左:地図、右:施設リスト。

メインエリアの上部にヘッダーバーを配置（HTML+CSS `st.markdown(unsafe_allow_html=True)`）。

##### ヘッダーバー仕様

- 高さ: 約 64px
- 背景色: `#7C3AED`（紫）
- 文字色: 白
- 左寄せパディング: 24px
- フォントサイズ: 22px、太字
- 文言: `{小売店名称} 周辺マップ概要 ｜ 半径{半径}km圏内`
- 角丸: 8px

##### 左カラム（地図）

- folium.Map 仕様
  - `location=[店舗緯度, 店舗経度]`
  - `zoom_start`: 半径から自動算出（下記式）
    - radius<=1 → 16
    - 1<radius<=2 → 15
    - 2<radius<=5 → 14
    - 5<radius<=10 → 13
    - 10< → 12
  - `tiles="OpenStreetMap"`
  - サイズ: `width=700`, `height=560`
- 円（半径）
  - `folium.Circle`
  - `radius` = 半径km × 1000
  - `color="#7C3AED"`, `weight=2`, `dash_array="8,8"`, `fill=True`, `fill_color="#7C3AED"`, `fill_opacity=0.08`
- 店舗マーカー
  - `folium.Marker`
  - 中心の店舗のみ表示
  - アイコン: `folium.Icon(color="black", icon="shopping-cart", prefix="fa")`
  - tooltip: 小売店名称
- 推進園マーカー（距離 ≤ 指定半径）
  - `folium.plugins.BeautifyIcon` を使用し番号入り円形マーカーで描画
  - 施設区分による色分け:

    | 施設区分 | background_color |
    |---|---|
    | 保育園 | `#22C55E`（緑） |
    | 幼稚園 | `#EF4444`（赤） |
    | こども園 | `#F59E0B`（黄） |

  - `border_color` は同色、`text_color="#FFFFFF"`、`number=連番`（1からの連番）
  - tooltip: `{連番}. {施設名称}（{距離}km）`
- 凡例（地図右下に固定）
  - HTML文字列を `m.get_root().html.add_child(folium.Element(...))` で挿入
  - 表示: `● 保育園`（緑） `● 幼稚園`（赤） `● こども園`（黄）

##### 右カラム（施設リスト）

上端に `施設リスト` ヘッダー（高さ40px、背景 `#7C3AED`、白文字、中央揃え、フォント16px太字）

その下に施設1件ごとにカードを縦積み:

- カードレイアウト（HTML+CSS）:
  - 左端に番号バッジ（24×24px、円形、施設区分色、白文字、中央揃え）
  - 右側に施設名称（太字 14px）と距離（淡色 12px、フォーマット `約{距離}km`）
  - 背景: `#FFFFFF`
  - 罫線: bottom 1px `#E5E7EB`
  - 上下パディング: 8px
- 並び順: 距離昇順
- 番号は地図マーカーと同一の連番（昇順インデックス）

##### 件数表示

ヘッダー直下に `st.metric("対象推進園数", f"{n}件")` を配置。

##### ボタン

施設リストの直下に2つのボタンを配置:

- `st.download_button("画像をダウンロード", data=png_bytes, file_name=f"{小売店名称}.png", mime="image/png")`
- `st.download_button("データをダウンロード", data=csv_bytes, file_name=f"{小売店名称}_{半径}km.csv", mime="text/csv")`

### 6.2 SC-02 マップ画面（企業一括）

#### 6.2.1 サイドバー入力

- 企業名称: `st.sidebar.selectbox`（`master.csv` の `企業名称` ユニーク値、昇順）
- 半径(km): `st.sidebar.number_input`（仕様は SC-01 と同一）
- 実行ボタン: `st.sidebar.button("ZIP生成")`

#### 6.2.2 メインエリア

- 上部ヘッダーバー（紫帯、SC-01 と同様）
  - 文言: `{企業名称} 一括出力 ｜ 半径{半径}km圏内`
- 対象店舗一覧テーブル（`st.dataframe`）
  - カラム: 小売店コード、小売店名称、対象推進園数
- 進捗バー: `st.progress`
- ZIP生成ロジック
  - 対象企業に属する全店舗（小売店コードのユニーク件数）について SC-01 と同一描画ロジックでPNGを生成
  - 1ファイル名: `{小売店名称}.png`
  - ZIPファイル名: `{企業名称}_{半径}km.zip`
- 完了後ボタン
  - `st.download_button("ZIPをダウンロード", data=zip_bytes, file_name=..., mime="application/zip")`
- 同時にデータZIPボタンも配置
  - 各店舗の対象データCSVをまとめたZIP
  - ZIPファイル名: `{企業名称}_{半径}km_data.zip`
  - 内部ファイル名: `{小売店名称}.csv`

### 6.3 SC-03 ヘルプ画面

メインエリアに以下を表示。

- タイトル: `データ出典`（h2）
- 本文（そのまま改行付きで表示。URLは `st.markdown` でハイパーリンク化）:

```
位置参照情報（大字町丁目・街区レベル）令和6年（国土交通省）、
電子国土基本図（地名情報）住居表示住所（国土地理院）、
Geolonia 住所データ（株式会社Geolonia） https://geolonia.github.io/japanese-addresses/、
アドレス・ベース・レジストリ（デジタル庁）
https://www.digital.go.jp/policies/base_registry_address_tos/
登記所備付地図データ（法務省）
をもとに、株式会社情報試作室が加工した
jageocoder 用住所データベース（住居表示レベル）を利用
```

## 7. 機能要件

| ID | 機能 | 入力 | 出力 |
|---|---|---|---|
| F-01 | 店舗単位マップ表示 | 小売店名称、半径(km) | 地図、件数、施設リスト |
| F-02 | 店舗単位画像ダウンロード | F-01 の表示状態 | `{小売店名称}.png` |
| F-03 | 店舗単位データダウンロード | F-01 の表示状態 | `{小売店名称}_{半径}km.csv` |
| F-04 | 企業単位画像一括ダウンロード | 企業名称、半径(km) | `{企業名称}_{半径}km.zip`（中身: 店舗ごとのPNG） |
| F-05 | 企業単位データ一括ダウンロード | 企業名称、半径(km) | `{企業名称}_{半径}km_data.zip`（中身: 店舗ごとのCSV） |
| F-06 | ヘルプ表示 | なし | データ出典の固定文言表示 |

## 8. データ処理仕様

### 8.1 マスタロード

```python
@st.cache_data
def load_master() -> pd.DataFrame:
    return pd.read_csv("data/master.csv")
```

### 8.2 絞込ロジック

```python
filtered = df[
    (df["小売店名称"] == store_name) &
    (df["距離"] <= radius_km)
].sort_values("距離").reset_index(drop=True)
filtered["連番"] = filtered.index + 1
```

件数は `len(filtered)`。重複除外は行わない。

### 8.3 PNG生成（画像ダウンロード仕様）

ダウンロードされるPNGは「ヘッダー帯 + 地図 + 施設リスト」を1枚に統合した合成画像とする。folium標準の `_to_png` は地図領域のみを出力するため、以下の手順で Pillow による合成を行う。

#### 処理フロー

1. `folium.Map._to_png(delay=3)` で地図のみのPNGバイト列を取得
   - 内部で selenium + Chromium が headless 起動する
2. Pillow で空のキャンバスを生成
3. キャンバス上にヘッダー帯・地図・施設リストを描画
4. PNGバイト列としてメモリ上に保持し、`st.download_button` に渡す

#### 合成キャンバス仕様

- 全体サイズ: 横 `1280px` × 縦 `720px`
- 背景色: `#FFFFFF`

##### ヘッダー帯領域（上端 0–64px）

- 背景色: `#7C3AED`
- 高さ: `64px`、横幅: `1280px`
- 文字: 白、フォントサイズ `22px`、太字
- 左パディング: `24px`、縦中央揃え
- 文言: `{小売店名称} 周辺マップ概要 ｜ 半径{半径}km圏内`

##### 地図領域（左 0–656px、上 64–720px）

- サイズ: `656px × 656px`
- folium生成PNGをそのままリサイズして貼付

##### 施設リスト領域（右 656–1280px、上 64–720px）

- サイズ: `624px × 656px`
- 上端 `64–104px`（高さ40px）に紫帯ヘッダー（背景 `#7C3AED`、白文字、中央揃え、`施設リスト`）
- その下に施設カード（高さ約 `56px` ／件）を縦積み
  - 左端に番号バッジ（直径 `24px`、円形、施設区分色、白文字中央揃え、左マージン `16px`）
  - 番号バッジ右に施設名称（太字 `14px`、`#111827`）と距離（`12px`、`#6B7280`、`約{距離}km`）
  - カード間: 下罫線 `1px` `#E5E7EB`
- 件数が多くカード描画領域を超える場合は、領域内で収まる範囲のみ描画し、末尾に `他 N 件` と表示

#### フォント

日本語表示のため IPAexゴシック（`ipaexg.ttf`）を `fonts/` 配下に同梱し、Pillow の `ImageFont.truetype("fonts/ipaexg.ttf", size)` で読み込むこと。

### 8.4 ZIP生成

```python
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for store in stores:
        png = build_png(store, radius)
        zf.writestr(f"{store}.png", png)
buf.seek(0)
```

## 9. ファイル構成

```
/
├ app.py                  # エントリ。ナビゲーション切替のみ
├ pages/
│  ├ map_single.py        # SC-01
│  ├ map_bulk.py          # SC-02
│  └ help.py              # SC-03
├ lib/
│  ├ data.py              # マスタロード、絞込
│  ├ map_builder.py       # folium.Map 生成
│  ├ png_builder.py       # PNG 合成（Pillow）
│  └ zip_builder.py       # ZIP 生成
├ data/
│  └ master.csv
├ fonts/
│  └ ipaexg.ttf
├ requirements.txt
└ app.yaml                # Databricks Apps 用設定（Chromium インストールを含む）
```

## 10. 非機能要件

| 項目 | 内容 |
|---|---|
| 応答時間 | 単一店舗マップ表示: 3秒以内 |
| 一括出力 | 100店舗 / 5分以内 |
| 同時利用 | 5ユーザー想定 |
| キャッシュ | `st.cache_data` でマスタCSVをキャッシュ |
| ログ | `logging` モジュールで INFO 以上を標準出力 |

## 11. エラーハンドリング

| 状況 | 挙動 |
|---|---|
| 対象データ0件 | `st.warning("該当する推進園がありません")` を表示し、地図と空の施設リストのみ表示 |
| マスタCSV読込失敗 | `st.error` で停止 |
| PNG生成失敗 | 該当店舗のみスキップしログ出力、ZIPには `errors.txt` を同梱して失敗店舗名を列挙 |

## 12. 受入条件

- [ ] SC-01 で店舗・半径を指定して地図と施設リストが表示される
- [ ] SC-01 から `{店舗名}.png`（ヘッダー＋地図＋施設リスト合成）がダウンロードできる
- [ ] SC-01 から `{店舗名}_{半径}km.csv` がダウンロードできる
- [ ] SC-02 で企業・半径を指定して全店舗PNGがZIPでダウンロードできる
- [ ] SC-02 で全店舗CSVがZIPでダウンロードできる
- [ ] SC-03 で出典文言が表示される
- [ ] Databricks Apps 上で起動・操作できる