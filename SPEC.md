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

### 4.1 データソース

- **種別:** Databricks Unity Catalog テーブル（Delta Table）
- **テーブル名:** `config/databricks_config.toml` の `[databricks] table` で指定（3 パート名 `catalog.schema.table`）
- **接続:** `DatabricksSession.builder.serverless(True).getOrCreate()`（Databricks Apps 内では自動クレデンシャル取得）
- **想定件数:** 約 5万行以上（店舗 × 推進園 の組合せ）
- **取得方式:** オンデマンド取得。起動時は全件をロードせず、企業名称の DISTINCT のみを軽量クエリで取得する。
  ユーザーが企業名称と取得半径を指定して「データ取得」を押下したとき、`企業名称 == 指定企業 AND 距離km <= 取得半径`
  を Spark 側で適用してから `toPandas()` で取得する（大量データの転送を回避）。

> **ローカル開発時:** `~/.databrickscfg` または環境変数 `DATABRICKS_HOST` / `DATABRICKS_TOKEN` を設定すること。

### 4.2 カラム定義

| カラム名 | 型 | 必須 | 説明 |
|---|---|---|---|
| 企業名称 | str | ○ | 例: ヨークベニマル |
| 業態名称 | str | ○ | 例: GMS |
| 店舗コード | str | ○ | 店舗一意キー |
| 店舗名称 | str | ○ | 例: アピタ千代田橋店 |
| 店舗_都道府県 | str | ○ | 店舗の都道府県（画像一括DLの絞込に使用） |
| 店舗住所 | str | ○ | 表示用 |
| 店舗lat | float | ○ | WGS84 |
| 店舗lon | float | ○ | WGS84 |
| 推進園名称 | str | ○ | 推進園名 |
| 推進園区分 | str | ○ | 区分文字列。値は `認可保育所` / `認定こども園` / `幼稚園` の3種。マーカー・施設リストの色分けに使用（§6.1.2）。想定外の値はフォールバック色 |
| 推進園_都道府県 | str | ○ | 推進園の都道府県 |
| 推進園住所 | str | ○ | 表示用 |
| 推進園lat | float | ○ | WGS84 |
| 推進園lon | float | ○ | WGS84 |
| 距離km | float | ○ | km、事前算出済み。値はフル精度で渡るため、表示時に小数第2位へ丸める |

### 4.3 前提

- 距離は事前計算済みのため、アプリ内で再計算しない
- 1店舗に対し複数行（施設数ぶん）存在する
- 距離による重複除外は行わず、そのまま件数化する

## 5. 画面構成

### 5.1 画面構成（単一ページ）

マルチページ（ラジオ切替）は廃止し、**単一ページ**に集約する。1ページ内に
上から「上部コントロール（企業名称・小売店名称・半径）＋企業一括ダウンロード2ボタン」→
「地図＋施設リスト」→「データ出典（フッタ、小さく）」を配置する。

Streamlit の自動マルチページ機能を使わないため、画面モジュールは `pages/` ではなく
`views/main_page.py` に置き、`app.py` から `render(df)` を呼ぶ（サイドバー・ラジオは使わない）。

## 6. 画面詳細

### 6.1 単一ページ レイアウト

#### 6.1.1 上部コントロール（メインエリア最上部）

`st.columns(3)` で横並びに配置:

- 企業名称: `st.selectbox`（`master.csv` の `企業名称` ユニーク値・昇順、index=None、
  プレースホルダ `企業を選択してください`）
- 小売店名称: `st.selectbox`（**選択中の企業で絞り込んだ** `小売店名称` ユニーク値・昇順、
  index=None、プレースホルダ `店舗を選択してください`）。企業未選択時は選択肢空。
- 半径(km): `st.number_input`（`min_value=0.1`, `max_value=50.0`, `value=2.0`, `step=0.1`）

企業名称の直下（同じ列）に企業一括ダウンロードを `st.expander("企業一括ダウンロード")`
（折りたたみ）で縦に配置する（§6.2）。

#### 6.1.2 メインエリア（地図＋施設リスト）

小売店名称が選択されたら表示する。`st.columns([2, 1])` で左:地図、右:施設リスト。
上部にヘッダーバーを配置（HTML+CSS `st.markdown(unsafe_allow_html=True)`）。

##### ヘッダーバー仕様

- 高さ: 約 64px
- 背景色: `#7C3AED`（紫）
- 文字色: 白
- 左寄せパディング: 24px
- フォントサイズ: 22px、太字
- 文言: `{小売店名称} 周辺マップ概要 ｜ 半径{半径}km圏内`
- 角丸: 8px

##### 左カラム（地図）

- 「マップをリセット」ボタンを**紫帯（周辺マップ概要）の上**に置く。誤操作（パン/ズーム）した際に
  押すと初期表示へ戻す（`st_folium` の `key` に nonce を含め、押下で nonce を増やして再マウントし
  `build_map` の初期位置/ズームに復帰させる）。
- folium.Map 仕様
  - `location=[店舗緯度, 店舗経度]`
  - `zoom_start`: 指定半径の円がビューポート内に収まるよう動的算出する。
    Web Mercator の解像度 `mpp = 156543.03392 * cos(緯度) / 2^z` を用い、円の直径
    `2 × radius_km × 1000`(m) がビューポート幅の約 80% に収まる最大ズームを採用する
    （`z = floor(log2(0.8 × viewport_px × 156543.03392 × cos(緯度) / 直径m))`、0〜19 にクランプ）。
    旧来の段階式（radius≤1→16 等）はズーム過大で半径円が画面外に出るため廃止。
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
  - `推進園区分` の値に応じて色分けする。色定義は `lib/colors.py` に一元化し、
    地図（folium）・ダウンロードPNG・静的PNG・施設リストで共有する。
    地図左下には区分を説明する凡例（`推進園区分`）を重ねて表示する。

    色は区別しやすさ（色覚多様性含む）を優先した高コントラストな3色を用いる。

    | 推進園区分 | background_color |
    |---|---|
    | 認可保育所 | `#2A78D6`（青） |
    | 認定こども園 | `#EB6834`（橙） |
    | 幼稚園 | `#4A3AA7`（紫） |
    | 上記以外 / 区分なし | `#6B7280`（灰、フォールバック） |

  - `border_color` は同色、`text_color="#FFFFFF"`、`number=連番`（1からの連番）
  - tooltip: `{連番}. {施設名称}（{距離:.2f}km）`（距離は小数第2位まで）

##### 右カラム（施設リスト）

上端に `施設リスト` ヘッダー（高さ40px、背景 `#7C3AED`、白文字、中央揃え、フォント16px太字）

その下に施設1件ごとにカードを縦積み:

- カードレイアウト（HTML+CSS）:
  - 左端に番号バッジ（24×24px、円形、施設区分色、白文字、中央揃え）
  - 右側に施設名称（太字 14px）と距離（淡色 12px、フォーマット `約{距離:.2f}km`、小数第2位まで）
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

### 6.2 企業一括ダウンロード（企業名称直下の折りたたみ）

企業名称の直下に `st.expander("企業一括ダウンロード")`（初期は折りたたみ）を置き、
「企業全体のもの」と分かるよう縦に配置する。表示順は **データダウンロード →
都道府県で絞り込み → 画像をダウンロード**。企業未選択時は各ボタン `disabled`。

- **データダウンロード**: 対象企業＋半径で絞り込んだデータを **1つのCSV**で出力する
  （都道府県選択時はその都道府県でも絞り込む）。
  - エンコーディング: **cp932**（Excel 互換。`to_csv(index=False).encode("cp932", errors="replace")`）
  - 内容: `企業名称==指定企業 かつ 距離<=半径`（＋選択都道府県）の全行を `小売店名称`・`距離`
    昇順で出力。ファイル名: `{企業名称}[_{都道府県}]_{半径}km.csv`、`st.download_button` で直接生成。
- **都道府県で絞り込み**: `st.multiselect`（選択肢は**選択企業の `都道府県` ユニーク値**、
  初期未選択）。大量画像の一括DLを防ぐため、画像DLはここで都道府県を選んだ分のみを対象とする。
- **画像をダウンロード**: 選択都道府県に属する全店舗について §6.1.2/§8.3 の描画で PNG を生成し
  ZIP にまとめる。生成は `@st.cache_data` で行い、**ボタン1つ（`st.download_button`）で完結**
  （生成→ダウンロード）。都道府県未選択時は `disabled`。
  - 1ファイル名: `{小売店名称}.png` / ZIPファイル名: `{企業名称}[_{都道府県}]_{半径}km.zip`

### 6.3 データ出典（フッタ）

ページ最下部に `st.divider()` の後、`st.caption` で小さく目立たない形で表示する（URLはリンク化）:

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
| F-01 | 店舗単位マップ表示 | 企業名称→小売店名称、半径(km) | 地図、件数、施設リスト |
| F-04 | 企業単位画像一括ダウンロード | 企業名称、半径(km) | `{企業名称}_{半径}km.zip`（中身: 店舗ごとのPNG） |
| F-05 | 企業単位データ一括ダウンロード | 企業名称、半径(km) | `{企業名称}_{半径}km.csv`（単一CSV、cp932、企業＋半径で絞込） |
| F-06 | データ出典表示 | なし | フッタに固定文言を小さく表示 |

※ 旧 F-02/F-03（店舗単位の画像/データダウンロード）は単一ページ化に伴い廃止。

## 8. データ処理仕様

### 8.1 データ取得（オンデマンド）

起動時に全件をロードせず、必要なデータだけを都度取得する。

```python
@st.cache_data(show_spinner="企業名称を取得中...")
def load_company_names() -> list[str]:
    """起動時の軽量クエリ: 企業名称の DISTINCT のみ。"""
    spark = DatabricksSession.builder.serverless(True).getOrCreate()
    rows = spark.table(table_name).select(company_col).distinct().toPandas()
    return sorted(rows[company_col].dropna().astype(str).tolist())


@st.cache_data(show_spinner="データを取得中...")
def load_filtered(company: str, fetch_radius_km: float) -> pd.DataFrame:
    """企業 + 取得半径で Spark 側を絞り込んで取得する。"""
    from pyspark.sql import functions as F
    spark = DatabricksSession.builder.serverless(True).getOrCreate()
    sdf = (
        spark.table(table_name)
        .where(F.col(company_col) == company)
        .where(F.col(distance_col) <= float(fetch_radius_km))
    )
    df = sdf.toPandas()
    # 列名マッピングを適用（config/column_mapping.toml）
    ...
    return df
```

- テーブル名は `config/databricks_config.toml` で管理する（`[databricks] table = "catalog.schema.table_name"`）。
- `load_filtered` は `@st.cache_data` により `(company, fetch_radius_km)` でキャッシュされる。
  同一条件の再押下はキャッシュヒット、条件変更時は新規クエリとなる。
- 取得結果は `st.session_state["loaded_df"]` に保持し、以降の絞込・地図表示はこの部分集合に対して
  インメモリで行う。

### 8.2 絞込ロジック

取得済み DF（取得半径以内）に対し、**表示半径**でさらにインメモリ絞込を行う
（表示半径 ≤ 取得半径。例: 5km で取得して 2km で表示）。

```python
filtered = df[
    (df["店舗名称"] == store_name) &
    (df["距離km"] <= display_radius_km)
].sort_values("距離km").reset_index(drop=True)
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

##### メトリクス帯領域（上端 64–104px、高さ 40px、全幅）

- 背景色: `#FFFFFF`
- 文言: `対象推進園数`（小さめ・`#6B7280`）＋ `{N}件`（太字・`#111827`）、左パディング `24px`、縦中央
- 画面（`st.metric`）と並びを合わせるため、ヘッダー帯と地図の間に配置する

##### 地図領域（左 0–656px、上 104–720px）

- サイズ: `656px × 616px`
- 地図PNGをこのサイズにリサイズして貼付

##### 施設リスト領域（右 656–1280px、上 104–720px）

- サイズ: `624px × 616px`
- 上端 `104–144px`（高さ40px）に紫帯ヘッダー（背景 `#7C3AED`、白文字、中央揃え、`施設リスト`）
- その下に施設カード（高さ約 `56px` ／件）を縦積み
  - 左端に番号バッジ（直径 `24px`、円形、施設区分色、白文字中央揃え、左マージン `16px`）
  - 番号バッジ右に施設名称（太字 `14px`、`#111827`）と距離（`12px`、`#6B7280`、`約{距離:.2f}km`、小数第2位まで）
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
├ app.py                  # エントリ。load_master + main_page.render のみ
├ views/                  # 画面（pages/ は使わない＝自動マルチページ回避）
│  └ main_page.py         # 単一ページ（コントロール＋一括DL＋地図＋施設リスト＋出典）
├ lib/
│  ├ data.py              # マスタロード（Databricks テーブル）、絞込、ズーム算出
│  ├ map_builder.py       # folium.Map 生成（画面内の対話地図）
│  ├ static_map.py        # ブラウザレス静的地図生成（PNG用、OSMタイル+Pillow）
│  ├ png_builder.py       # PNG 合成（Pillow）
│  └ zip_builder.py       # 画像ZIP 生成
├ config/
│  ├ column_mapping.toml  # アプリ列名 ↔ テーブル列名マッピング
│  └ databricks_config.toml  # Databricks テーブル名設定
├ fonts/
│  └ ipaexg.ttf
├ requirements.txt
└ app.yaml                # Databricks Apps 用設定
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

- [ ] 単一ページで、企業選択により小売店名称が絞り込まれる（カスケード）
- [ ] 店舗・半径を指定して地図と施設リストが表示される（指定半径の円が地図内に収まる）
- [ ] 企業一括データダウンロードで単一CSV（cp932）`{企業名称}_{半径}km.csv` が取得できる
- [ ] 企業一括画像ダウンロードで全店舗PNGの ZIP `{企業名称}_{半径}km.zip` が取得できる
- [ ] ページ最下部に出典が小さく表示される
- [ ] ラジオ/サイドバーナビが無く、単一ページで完結する
- [ ] Databricks Apps 上で起動・操作できる