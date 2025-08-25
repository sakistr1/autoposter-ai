import os, json, base64
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE = Path(__file__).resolve().parent.parent
TPL_DIR = BASE / "templates"
STATIC_DIR = BASE / "static"
OUT_PREV = STATIC_DIR / "generated" / "previews"
OUT_FINAL = STATIC_DIR / "generated" / "finals"
OUT_PREV.mkdir(parents=True, exist_ok=True)
OUT_FINAL.mkdir(parents=True, exist_ok=True)

env = Environment(
    loader=FileSystemLoader(str(TPL_DIR)),
    autoescape=select_autoescape(("svg", "xml"))
)

def _load_meta(template_id: str):
    with open(TPL_DIR / template_id / "meta.json", "r", encoding="utf-8") as f:
        return json.load(f)

def _render_svg(template_id: str, ctx: dict) -> str:
    tmpl = env.get_template(f"{template_id}/template.svg")
    return tmpl.render(**ctx)

def _add_watermark(svg: str, text="PREVIEW — Autopost AI") -> str:
    wm = ('<text x="20" y="1060" fill="#ffffff55" font-size="28" '
          'font-family="NotoSans, sans-serif">'+text+'</text>')
    return svg.replace("</svg>", wm + "</svg>")

def _b64_of_file(p):
    if not p:
        return None
    try:
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

def build_context(template_id: str, product: dict | None, params: dict | None):
    meta = {}
    try:
        meta = _load_meta(template_id)
    except Exception:
        pass
    ctx = {"size": meta.get("size", {"w":1080,"h":1080})}
    ctx.update(meta.get("defaults", {}))
    if params:
        ctx.update(params)

    if product:
        ctx["product_name"] = product.get("name") or ctx.get("product_name") or "Προϊόν"
        ctx["price"] = product.get("price") or ctx.get("price") or "€0,00"
        ctx["image_base64"] = _b64_of_file(product.get("image_path"))
    else:
        ctx.setdefault("product_name", "Demo Προϊόν")
        ctx.setdefault("price", "€9,99")
        ctx["image_base64"] = None
    return ctx

def render_preview(template_id: str, product: dict | None, params: dict | None) -> str:
    svg = _render_svg(template_id, build_context(template_id, product, params))
    svg = _add_watermark(svg)
    name = f"preview_{os.urandom(16).hex()}.svg"
    (OUT_PREV / name).write_text(svg, encoding="utf-8")
    return "/static/generated/previews/" + name

def render_final(template_id: str, product: dict | None, params: dict | None) -> str:
    svg = _render_svg(template_id, build_context(template_id, product, params))
    name = f"final_{os.urandom(16).hex()}.svg"
    (OUT_FINAL / name).write_text(svg, encoding="utf-8")
    return "/static/generated/finals/" + name
