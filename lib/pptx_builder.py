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
load_caption(store)                     -- config の定型文に小売店名称を差し込んだ文字列を返す
build_store_pptx(template_bytes, png, caption)
                                        -- 画像プレースホルダーに地図PNGを挿入し、テキスト
                                           プレースホルダーへ caption を入れて pptx bytes を返す
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


def load_caption(store: str | None) -> str:
    """選択中の小売店名称 *store* をテーマの定型文に差し込んだキャプション文字列を返す。

    定型文はテーマ設定（``config/theme.toml`` の ``[pptx] store_caption_format``、テーマ設定
    ページで編集可）。``{store}`` が小売店名称に置換される。*store* が空/None のときは
    空文字を返す（テキスト挿入なし）。書式不正時は店舗名のみを返す。
    """
    if not store:
        return ""
    from lib import colors  # noqa: PLC0415

    fmt = colors.store_caption_format()
    try:
        return fmt.format(store=store)
    except (KeyError, IndexError, ValueError) as e:  # noqa: PERF203
        logger.warning("store_caption_format の書式が不正です（%r）: %s", fmt, e)
        return store


def _target_box(slide, prs):
    """画像を収める矩形 (left, top, width, height) を返し、対象プレースホルダーを削除する。

    画像プレースホルダー（``insert_picture`` 可）を最優先し、無ければ最初のプレースホルダー、
    それも無ければスライド全面を対象にする。プレースホルダーは空枠が残らないよう削除する。
    """
    picture_ph = None
    for ph in slide.placeholders:
        if hasattr(ph, "insert_picture"):
            picture_ph = ph
            break
    target = picture_ph or (slide.placeholders[0] if len(slide.placeholders) else None)
    if target is not None:
        box = (target.left, target.top, target.width, target.height)
        target._element.getparent().remove(target._element)
        return box
    return (0, 0, prs.slide_width, prs.slide_height)


def _fill_text_placeholder(slide, text: str) -> None:
    """スライドのテキストプレースホルダーに *text* を書き込む。

    画像プレースホルダー（``insert_picture`` 可）は対象外とし、``text_frame`` を持つ
    最初のプレースホルダーへ書き込む。テンプレによって idx/名前が異なりうるため idx は
    ハードコードせず、型/能力ベースで検出する。対象が無ければ warning を出してスキップする。
    """
    for ph in slide.placeholders:
        if hasattr(ph, "insert_picture"):
            continue
        if ph.has_text_frame:
            ph.text_frame.text = text
            return
    logger.warning("テキストプレースホルダーが見つかりませんでした（caption=%r）", text)


def build_store_pptx(
    template_bytes: bytes, map_png_bytes: bytes, caption_text: str | None = None
) -> bytes:
    """Place *map_png_bytes* into the template's picture placeholder → pptx bytes.

    地図PNGを 1 枚目スライドの画像プレースホルダー位置へ貼り付ける。プレースホルダーの
    ``insert_picture`` は画像をプレースホルダーのアスペクト比にクロップしてしまい、対話地図と
    体裁が合わなくなる（issue 202607221245）。そこで、プレースホルダーの矩形内に **アスペクト比を
    保ったまま**収まるよう ``add_picture`` で中央配置する（元プレースホルダーは削除）。

    *caption_text* が指定された場合は、テキストプレースホルダーへその文字列を書き込む
    （issue 202607221450）。画像プレースホルダーとは別枠のため画像貼り付けと干渉しない。
    """
    from PIL import Image  # noqa: PLC0415
    from pptx import Presentation  # noqa: PLC0415

    prs = Presentation(io.BytesIO(template_bytes))
    slide = prs.slides[0]

    if caption_text:
        _fill_text_placeholder(slide, caption_text)

    box_left, box_top, box_w, box_h = _target_box(slide, prs)

    # 画像のアスペクト比を保って矩形にフィット（レターボックス）し、矩形中央へ配置する。
    with Image.open(io.BytesIO(map_png_bytes)) as im:
        img_w, img_h = im.size
    scale = min(box_w / img_w, box_h / img_h)
    draw_w = int(round(img_w * scale))
    draw_h = int(round(img_h * scale))
    left = int(box_left + (box_w - draw_w) / 2)
    top = int(box_top + (box_h - draw_h) / 2)

    slide.shapes.add_picture(
        io.BytesIO(map_png_bytes), left, top, width=draw_w, height=draw_h
    )

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
