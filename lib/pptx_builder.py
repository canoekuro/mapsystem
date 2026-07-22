"""
商談用資料 / 店舗POP の PowerPoint (pptx) 生成（issue 202607221128）。

選択中の1店舗について、地図画像（``lib.static_map.render_static_map`` の出力）を
テンプレートの画像プレースホルダーに貼り付けた pptx を1枚生成する。

テンプレートは Databricks の Unity Catalog Volume から取得する（``lib/volume.py`` と
同じ WorkspaceClient パターン）。ローカル開発など Volume にアクセスできない場合は
リポジトリ同梱の ``images/template.pptx`` にフォールバックする。

Functions
---------
load_template_bytes(kind)               -- Volume からテンプレ取得（失敗時ローカルfallback）
build_store_pptx(template_bytes, png)   -- 画像プレースホルダーに地図PNGを挿入して pptx bytes を返す
"""

import io
import logging
import tomllib

logger = logging.getLogger(__name__)

_CONFIG_PATH = "config/databricks_config.toml"

# kind -> config キー（テンプレートファイル名）
_TEMPLATE_KEY = {
    "shoudan": "shoudan_template",
    "pop": "pop_template",
}


def _load_pptx_config() -> dict:
    """Load the [pptx] section from config/databricks_config.toml."""
    try:
        with open(_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("pptx", {})
    except FileNotFoundError:
        return {}


def load_template_bytes(kind: str) -> bytes:
    """Return the template pptx bytes for *kind* ("shoudan" or "pop").

    まず ``template_dir/{kind のテンプレファイル名}`` を Volume から取得し、失敗した場合は
    ``local_fallback``（既定 ``images/template.pptx``）を読む。Databricks 上では
    WorkspaceClient が自動でクレデンシャルを取得する。
    """
    if kind not in _TEMPLATE_KEY:
        raise ValueError(f"unknown template kind: {kind!r}")

    config = _load_pptx_config()
    template_dir = config.get("template_dir", "")
    filename = config.get(_TEMPLATE_KEY[kind], "")
    local_fallback = config.get("local_fallback", "images/template.pptx")

    if template_dir and filename:
        path = f"{template_dir.rstrip('/')}/{filename}"
        try:
            from databricks.sdk import WorkspaceClient  # noqa: PLC0415

            w = WorkspaceClient()
            resp = w.files.download(path)
            data = resp.contents.read()
            logger.info("テンプレートを取得しました: %s", path)
            return data
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Volume からのテンプレ取得に失敗（%s）。ローカルfallbackを使用: %s",
                path,
                e,
            )

    with open(local_fallback, "rb") as f:
        return f.read()


def _find_picture_placeholder(slide):
    """Return the picture placeholder shape on *slide*, or None.

    python-pptx は画像プレースホルダー（PICTURE / CLIP_ART）を ``insert_picture`` を持つ
    ``PicturePlaceholder`` として公開する。``insert_picture`` 属性の有無で判定する。
    """
    for ph in slide.placeholders:
        if hasattr(ph, "insert_picture"):
            return ph
    return None


def build_store_pptx(template_bytes: bytes, map_png_bytes: bytes) -> bytes:
    """Insert *map_png_bytes* into the template's picture placeholder → pptx bytes.

    テンプレの1枚目スライドにある画像プレースホルダーへ地図PNGを挿入する。
    ``insert_picture`` が使える画像プレースホルダーがあればそれを優先し、無い場合は
    プレースホルダーの位置・サイズに ``add_picture`` で貼り付けて元プレースホルダーを
    削除するフォールバックを用いる（テンプレ構成差異への堅牢性）。
    """
    from pptx import Presentation  # noqa: PLC0415

    prs = Presentation(io.BytesIO(template_bytes))
    slide = prs.slides[0]

    ph = _find_picture_placeholder(slide)
    if ph is not None:
        ph.insert_picture(io.BytesIO(map_png_bytes))
    else:
        # フォールバック: 最初のプレースホルダー位置に画像を貼り、元枠は削除する。
        placeholders = list(slide.placeholders)
        if placeholders:
            target = placeholders[0]
            left, top, width, height = (
                target.left,
                target.top,
                target.width,
                target.height,
            )
            target._element.getparent().remove(target._element)
        else:
            # プレースホルダーが無ければスライド全面に貼る。
            left, top = 0, 0
            width, height = prs.slide_width, prs.slide_height
        slide.shapes.add_picture(
            io.BytesIO(map_png_bytes), left, top, width=width, height=height
        )

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
