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
上から「上部コントロール（企業名称・取得半径・データ取得ボタン、取得後に都道府県・小売店名称）
＋データダウンロード」→「地図＋施設リスト」→「データ出典（フッタ、小さく）」を配置する。

Streamlit の自動マルチページ機能を使わないため、画面モジュールは `pages/` ではなく
`views/main_page.py` に置き、`app.py` から `render(df)` を呼ぶ（サイドバー・ラジオは使わない）。

## 6. 画面詳細

### 6.1 単一ページ レイアウト

#### 6.1.1 上部コントロール（メインエリア最上部）

オンデマンド取得のため、コントロールは「取得行（常時表示）」と「表示行（取得後のみ）」の2段に分ける。

**取得行**（`st.columns([2, 1, 1])`）:

- 企業名称: `st.selectbox`（`企業名称` ユニーク値・昇順、index=None、
  プレースホルダ `企業を選択してください`）
- 取得半径(km): `st.number_input`（`min_value=0.1`, `max_value=50.0`, `value=None`, `step=0.1`）
- データ取得: `st.button`（企業・取得半径が揃うまで `disabled`）。押下で
  `企業名称 == 指定企業 AND 距離km <= 取得半径` を Spark 側で絞り込んで取得する（§8.1）。
  取得結果は `st.session_state` に保持する。

**表示行**（`st.columns([1, 2])`、取得後のみ表示）:

- 都道府県: `st.selectbox`（**取得済みデータの `店舗_都道府県` ユニーク値**・昇順、index=None、
  プレースホルダ `都道府県で絞り込み（任意）`）。**単一選択・任意**で、小売店名称の候補を絞る。
- 小売店名称: `st.selectbox`（都道府県選択時はその県、未選択時は取得済み企業全体の
  `小売店名称` ユニーク値・昇順、index=None、プレースホルダ `店舗を選択してください`）。

取得行の下（小売店名称より上）にデータダウンロードを `st.expander("データダウンロード")`
（折りたたみ）で縦に配置する（§6.2）。

> 表示半径は廃止した。取得半径がそのまま表示半径となり、地図・施設リストは取得半径で描画する。

#### 6.1.2 メインエリア（地図＋施設リスト）

小売店名称が選択されたら表示する。`st.columns([2, 1])` で左:地図、右:施設リスト。
上部にヘッダーバーを配置（HTML+CSS `st.markdown(unsafe_allow_html=True)`）。

##### ヘッダーバー仕様

- 高さ: 約 64px
- 背景色: `band_color`（既定 `#7C3AED` 紫、テーマで調整可）
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
    （`z = floor(log2(0.8 × viewport_px × 156543.03392 × cos(緯度) / 直径m))`、0〜`max_zoom` にクランプ）。
    `max_zoom` は選択中ベースマップの最大ズーム（GSI 等は OSM の 19 未満）で、提供されない
    ズームのタイルを要求しないようにする。旧来の段階式（radius≤1→16 等）は廃止。
  - `tiles`/`attr`/`max_zoom`: 選択中のベースマップ（`lib/basemaps.py` の catalog、`config/theme.toml`
    `[map] basemap` で指定・テーマ設定ページで変更可）から取得する。帰属表示（`attr`）を地図に表示する。
    背景の選択肢: **OSM**（標準 / Humanitarian）・**国土地理院**（標準 / 淡色 / 航空写真 / 白地図）・
    **CARTO(OSMベース)**（Positron / Voyager / Dark Matter）。いずれもラスターXYZタイル。
  - サイズ: `width`/`height`（既定 `700×560`）。`config/theme.toml` `[map] map_width`/`map_height`
    で指定・テーマ設定ページで変更可。`lib/colors.map_width()`/`map_height()` で描画時に解決し、
    `st_folium`（`views/main_page.py`）と `folium.Map`（`lib/map_builder.py`）へ同一値を渡す。
    `zoom_for_radius` の `viewport_px` も高さに連動する。
- 円（半径）
  - `folium.Circle`
  - `radius` = 半径km × 1000
  - `color`/`fill_color`=`circle_color`（既定 `#7C3AED`）, `weight=2`, `dash_array="8,8"`,
    `fill=True`, `fill_opacity`=`circle_fill_opacity`（既定 `0.08`）。いずれもテーマで調整可。
- 店舗マーカー
  - `folium.Marker`
  - 中心の店舗のみ表示
  - アイコン: `folium.plugins.BeautifyIcon`（`icon="shopping-cart"`, `icon_shape="marker"`,
    背景/枠=`store_marker_color`（既定 `#111827`、テーマで調整可）, 文字色 白）。
    任意の hex 色を指定できるよう `folium.Icon`（名前付き色のみ）ではなく BeautifyIcon を用いる。
  - tooltip: 小売店名称
- 推進園マーカー（距離 ≤ 指定半径）
  - `folium.plugins.BeautifyIcon` を使用し番号入り円形マーカーで描画
  - `推進園区分` の値に応じて色分けする。色定義は `lib/colors.py`（テーマ）に一元化し、
    地図（folium）・ダウンロードPNG・静的PNG・施設リストで共有する。既定値は
    `config/theme.toml` に置き、「テーマ設定」ページ（§6.4）から調整できる。
    地図左下には区分を説明する凡例（`推進園区分`）を重ねて表示する。

    色は区別しやすさ（色覚多様性含む）を優先した高コントラストな3色を既定とする。

    | 推進園区分 | background_color（既定） |
    |---|---|
    | 認可保育所 | `#2A78D6`（青） |
    | 認定こども園 | `#EB6834`（橙） |
    | 幼稚園 | `#4A3AA7`（紫） |
    | 上記以外 / 区分なし | `#6B7280`（灰、フォールバック） |

  - `border_color` は同色、`text_color="#FFFFFF"`、`number=連番`（1からの連番）
  - tooltip: `{連番}. {施設名称}（{距離:.2f}km）`（距離は小数第2位まで）

##### 右カラム（施設リスト）

上端に `施設リスト` ヘッダー（高さ40px、背景 `band_color`（既定 `#7C3AED`、テーマで調整可）、白文字、中央揃え、フォント16px太字）

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

### 6.4 テーマ設定ページ（`views/config_page.py`）

`st.navigation` の別ページ「テーマ設定」。配色と地図の背景を画面から調整する。

**表示制御:** このページの表示/非表示は `config/app_config.toml` の `[ui] show_theme_page` で
切り替える（既定 `false` = 非表示）。`app.py` は `lib/app_config.show_theme_page()` が `true` の
ときだけ「テーマ設定」ページをナビゲーションに登録する。運用中に配色・地図背景を編集させたい
場合のみ `true` にする。

- 調整対象（配色）: 推進園区分の色（凡例・マーカー）、区分フォールバック色、半径円の線色、
  半径円の塗り透明度（`st.slider` 0.0–0.5）、見出し帯・施設リストヘッダー色、店舗マーカー色。
  色は `st.color_picker` で選ぶ。
- 調整対象（地図の背景）: **提供元**（OpenStreetMap / 国土地理院 / CARTO）→ **スタイル** の
  2段 `st.selectbox`。選択肢は `lib/basemaps.py` の catalog。既定値は `config/theme.toml` `[map] basemap`。
- 調整対象（地図サイズ）: 対話地図（画面表示）の幅・高さ（px）を `st.number_input` 2つで指定
  （幅 500–1200 / 高さ 400–1000、既定 `700×560`）。`config/theme.toml` `[map] map_width`/`map_height`
  に保存し、対話地図へ反映する（ダウンロードPNGは対象外）。
- プレビュー: 選択中の配色で見出し帯・凡例・施設リストバッジ・半径円＋店舗を HTML で表示。
  地図の背景は選択中スタイル名と帰属表示を `st.caption` で示す。
- 保存: 「保存」で `config/theme.toml` の `[theme]`・`[map]` を書き換える（`lib/colors.save_theme`）。
  読取専用FS（Databricks Apps 等）で書き込みに失敗した場合はプロセス内へ適用しつつ、
  「設定TOMLをダウンロード」で得た内容をリポジトリにコミットして恒久化するよう促す。
- 「既定に戻す」で組み込み既定（`lib/colors._DEFAULTS`）へ戻す。
- 反映範囲: テーマ・背景は描画時に解決するため、保存後は地図・ダウンロードPNGの双方へ反映される。

## 7. 機能要件

| ID | 機能 | 入力 | 出力 |
|---|---|---|---|
| F-01 | 店舗単位マップ表示 | 企業名称→小売店名称、半径(km) | 地図、件数、施設リスト |
| F-04 | 企業単位画像一括ダウンロード | 企業名称、半径(km) | `{企業名称}_{半径}km.zip`（中身: 店舗ごとのPNG） |
| F-05 | 企業単位データ一括ダウンロード | 企業名称、半径(km) | `{企業名称}_{半径}km.csv`（単一CSV、cp932、企業＋半径で絞込） |
| F-06 | データ出典表示 | なし | フッタに固定文言を小さく表示 |
| F-07 | テーマ設定 | 各色・透明度・地図の背景 | `config/theme.toml`（`[theme]`/`[map]`）を更新し地図/PNGへ反映 |

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

**表示半径は廃止**し、取得半径をそのまま表示に用いる（取得半径 ＝ 表示半径）。取得済み DF
（取得半径以内）に対し、店舗名称でインメモリ絞込を行い、施設リスト・地図を描画する。

小売店名称の選択肢は、都道府県（任意・単一選択）で絞り込める。都道府県を選んだ場合は
`店舗_都道府県 == 指定県` の店舗のみ、未選択なら取得済み企業全体の店舗が候補になる。

```python
# 小売店候補（都道府県で任意に絞込）
store_opts = (
    stores_for_company_prefectures(df, company, [pref]) if pref
    else stores_for_company(df, company)
)

# 選択店舗の施設（取得半径をそのまま用いる）
filtered = df[
    (df["店舗名称"] == store_name) &
    (df["距離km"] <= fetch_radius_km)
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

- 背景色: `band_color`（既定 `#7C3AED`、テーマで調整可）
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
- 地図タイルは選択中ベースマップ（§6.1.2 と共通、`lib/basemaps.py`）から取得。左下に推進園区分の
  凡例、**右下にタイル提供元の帰属表示**（OSM/GSI/CARTO とも必須）を焼き込む。
- 地図PNGをこのサイズにリサイズして貼付

##### 施設リスト領域（右 656–1280px、上 104–720px）

- サイズ: `624px × 616px`
- 上端 `104–144px`（高さ40px）に帯ヘッダー（背景 `band_color`（既定 `#7C3AED`、テーマで調整可）、白文字、中央揃え、`施設リスト`）
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
├ app.py                  # エントリ。st.navigation でマップ/データ更新（+テーマ設定は config で出し分け）
├ views/                  # 画面（pages/ は使わない＝自動マルチページ回避）
│  ├ main_page.py         # マップページ（コントロール＋一括DL＋地図＋施設リスト＋出典）
│  ├ upload_page.py       # データ更新（Excel を Volume へ格納）
│  └ config_page.py       # テーマ設定（配色・地図の背景の調整・保存）
├ lib/
│  ├ data.py              # マスタロード（Databricks テーブル）、絞込、ズーム算出
│  ├ app_config.py        # UI表示設定（config/app_config.toml を読む。テーマ設定タブの出し分け）
│  ├ colors.py            # 配色テーマ＋地図背景の単一の入口（config/theme.toml を読む）
│  ├ basemaps.py          # 地図ベースマップ（背景タイル）のカタログ（OSM/GSI/CARTO）
│  ├ map_builder.py       # folium.Map 生成（画面内の対話地図）
│  ├ static_map.py        # ブラウザレス静的地図生成（PNG用、XYZタイル+Pillow）
│  ├ png_builder.py       # PNG 合成（Pillow）
│  ├ volume.py            # Unity Catalog Volume 書き込み（アップロード）
│  └ zip_builder.py       # 画像ZIP 生成
├ config/
│  ├ app_config.toml      # UI表示設定（[ui] show_theme_page 等）
│  ├ column_mapping.toml  # アプリ列名 ↔ テーブル列名マッピング
│  ├ databricks_config.toml  # Databricks テーブル名・Volume パス設定
│  └ theme.toml           # 配色テーマ（テーマ設定ページで更新）
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