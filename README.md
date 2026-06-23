# 店舗周辺マップ

担当小売店周辺の施設（推進園）を地図上に可視化し、流通・個店提案に活用するための
Web アプリケーション（Streamlit + folium / Databricks Apps 向け）。仕様は
[`SPEC.md`](SPEC.md)（マップアプリ 実装仕様書 v1.0）を正とする。

## 画面

| ID | 画面名 | 内容 |
|---|---|---|
| SC-01 | 店舗周辺マップ | 店舗・半径を指定し、地図／件数／施設リストを表示。PNG・CSV ダウンロード |
| SC-02 | 企業一括出力 | 企業・半径を指定し、全店舗の PNG／CSV を ZIP で一括出力 |
| SC-03 | ヘルプ | データ出典の表示 |

## ファイル構成

```
app.py                  # エントリ。サイドバーのナビゲーション切替
pages/                  # 画面（SC-01/02/03、各 render(df) を公開）
lib/data.py             # マスタロード・絞込（SPEC §8）
lib/map_builder.py      # folium.Map 生成（SPEC §6.1.2）
lib/png_builder.py      # PNG 合成（Pillow、SPEC §8.3）
lib/zip_builder.py      # ZIP 生成（SPEC §8.4）
data/master.csv         # 入力データ（SPEC §4）
fonts/ipaexg.ttf        # 日本語フォント（IPAexゴシック）
scripts/gen_sample.py   # サンプル master.csv 生成スクリプト
requirements.txt        # Python 依存
app.yaml                # Databricks Apps 設定
```

## ローカル実行

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
# サンプルデータを生成（本番 CSV がある場合は data/master.csv を差し替え）
venv/bin/python scripts/gen_sample.py
venv/bin/streamlit run app.py
```

PNG 生成（SC-01 の画像ダウンロード、SC-02 の画像 ZIP）には、ヘッドレス Chrome／
Chromium が必要（selenium 4 が chromedriver を自動解決）。地図タイルの取得に
OpenStreetMap への外部アクセスが必要。

## データ

- 入力は `data/master.csv`（UTF-8 BOM 無）。カラム定義は SPEC §4.2。
- 距離は事前算出済み（アプリ内で再計算しない）。1 店舗 = 複数行。
- 同梱の `data/master.csv` は `scripts/gen_sample.py` が生成したサンプル（名古屋圏、
  3 企業 10 店舗）。本番運用時は同スキーマの実データに差し替える。

## デプロイ時の留意事項

- **Chromium 本体**: `app.yaml` は Databricks Apps の起動コマンドのみを定義する。
  PNG／画像 ZIP 機能はランタイムに Chrome/Chromium 本体が存在することを前提とする。
  標準ランタイムに含まれない場合は、ベースイメージでのインストール、または事前同梱
  バイナリのパスを `CHROME_BIN` で指定する必要がある（既知リスク）。
- **フォント**: `fonts/ipaexg.ttf`（IPAexゴシック、IPA Font License）を同梱。PNG 合成の
  日本語描画に使用する。

## フォントのライセンス

`fonts/ipaexg.ttf` は IPAex ゴシック（IPA Font License Agreement v1.0）。
再配布条件は同ライセンスに従う。
