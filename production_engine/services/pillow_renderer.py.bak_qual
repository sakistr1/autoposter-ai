# production_engine/services/pillow_renderer.py
from __future__ import annotations
import io, math, os, json
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import urllib.request

ASSETS_DIR = os.getenv("ASSETS_DIR", "assets")
FONTS_DIR  = os.path.join(ASSETS_DIR, "fonts")
PALETTES   = os.path.join(ASSETS_DIR, "palettes.json")

# -------- helpers --------

def _load_palettes() -> Dict[str, Dict[str, str]]:
    try:
        with open(PALETTES, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"default":{
            "title_color":"#FFFFFF","price_color":"#00D084","cta_bg":"#111827","cta_text":"#FFFFFF",
            "badge_bg":"#EF4444","badge_text":"#FFFFFF","overlay_rgba":"0,0,0,120"}}

def _get_palette(mapping: Dict[str, Any]) -> Dict[str, str]:
    pal = _load_palettes()
    key = mapping.get("brand") or mapping.get("palette") or "default"
    base = pal.get("default", {})
    out = dict(base)
    out.update(pal.get(key, {}))
    # explicit overrides win
    for k in ("title_color","price_color","cta_bg","cta_text","badge_bg","badge_text","overlay_rgba"):
        if k in mapping: out[k] = mapping[k]
    return out

def _fetch_image(image_url: str) -> Image.Image:
    if image_url.startswith("http"):
        with urllib.request.urlopen(image_url, timeout=10) as r:
            data = r.read()
        return Image.open(io.BytesIO(data)).convert("RGB")
    return Image.open(image_url).convert("RGB")

def _target_size_for_ratio(ratio: str) -> Tuple[int,int]:
    ratios = {"1:1": (1080,1080), "4:5": (1080,1350), "9:16": (1080,1920)}
    return ratios.get(ratio or "4:5", (1080,1350))

def _cover_resize(img: Image.Image, tw: int, th: int) -> Image.Image:
    # cover strategy
    w,h = img.size
    scale = max(tw/w, th/h)
    nw, nh = int(w*scale), int(h*scale)
    img = img.resize((nw,nh), Image.LANCZOS)
    x = (nw - tw)//2
    y = (nh - th)//2
    return img.crop((x,y,x+tw,y+th))

def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:    return ImageFont.truetype(path, size=size, layout_engine=ImageFont.LAYOUT_BASIC)
    except: return ImageFont.truetype(os.path.join(FONTS_DIR,"NotoSans-Regular.ttf"), size=size)

def _best_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    candidates = []
    if bold:
        candidates += ["NotoSans-Bold.ttf","Inter-Bold.ttf","NotoSans-Regular.ttf"]
    else:
        candidates += ["NotoSans-Regular.ttf","Inter-Regular.ttf"]
    for fn in candidates:
        p = os.path.join(FONTS_DIR, fn)
        if os.path.exists(p):
            return _font(p, size)
    # fallback
    return ImageFont.load_default()

def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy: Tuple[int,int,int,int], radius: int, fill: str, outline: Optional[str]=None, width: int=1):
    x1,y1,x2,y2 = xy
    w = x2-x1; h = y2-y1
    r = max(0, min(radius, min(w,h)//2))
    draw.rounded_rectangle(xy, r, fill=fill, outline=outline, width=width)

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int,int]:
    if not text: return (0,0)
    bbox = draw.textbbox((0,0), text, font=font, stroke_width=0)
    return (bbox[2]-bbox[0], bbox[3]-bbox[1])

def _luminance(hex_color: str) -> float:
    c = hex_color.lstrip("#")
    r,g,b = tuple(int(c[i:i+2],16) for i in (0,2,4))
    for v in (r,g,b):
        pass
    # relative luminance
    def chan(u): 
        u/=255.0
        return u/12.92 if u<=0.03928 else ((u+0.055)/1.055)**2.4
    return 0.2126*chan(r)+0.7152*chan(g)+0.0722*chan(b)

def _auto_text_on(bg_hex: str) -> str:
    # contrast-based text color
    return "#111827" if _luminance(bg_hex) > 0.5 else "#FFFFFF"

def _rgba_tuple(s: str) -> Tuple[int,int,int,int]:
    try:
        r,g,b,a = [int(x.strip()) for x in s.split(",")]
        return (r,g,b,a)
    except:
        return (0,0,0,120)

# -------- main render --------

def render(
    image_url: str,
    mapping: Dict[str, Any],
    ratio: str = "4:5",
    watermark: bool = True
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    mapping keys (ό,τι έχεις ήδη + νέα):
      - title, price, old_price, discount_badge, cta
      - title_color, price_color, cta_bg, cta_text, badge_bg, badge_text
      - overlay_rgba (e.g. "0,0,0,140"), brand/palette
      - typography (optional): {title_size, price_size, cta_size, badge_size}
    """
    pal = _get_palette(mapping or {})
    W,H = _target_size_for_ratio(ratio)

    base = _fetch_image(image_url)
    canvas = _cover_resize(base, W,H)

    # overlay (optional)
    ov = pal.get("overlay_rgba")
    if ov:
        overlay = Image.new("RGBA", (W,H), _rgba_tuple(ov))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(canvas)

    # fonts / sizes
    typo = mapping.get("typography", {})
    title_size = int(typo.get("title_size", H*0.06))     # 6% ύψους
    price_size = int(typo.get("price_size", H*0.07))
    cta_size   = int(typo.get("cta_size",   H*0.045))
    badge_size = int(typo.get("badge_size", H*0.04))

    f_title = _best_font(bold=True,  size=title_size)
    f_price = _best_font(bold=True,  size=price_size)
    f_old   = _best_font(bold=False, size=max(int(price_size*0.7), 18))
    f_cta   = _best_font(bold=True,  size=cta_size)
    f_badge = _best_font(bold=True,  size=badge_size)

    pad = int(H*0.03)   # βασικό padding
    pad_small = max(8, int(H*0.015))

    # --- discount badge (top-left) ---
    badge = mapping.get("discount_badge") or ""
    if badge:
        tw,th = _text_size(draw, badge, f_badge)
        bx1 = pad; by1 = pad
        bx2 = bx1 + tw + pad_small*2
        by2 = by1 + th + pad_small*1
        badge_bg = pal["badge_bg"]
        badge_text = pal.get("badge_text") or _auto_text_on(badge_bg)
        _draw_rounded_rect(draw, (bx1,by1,bx2,by2), radius=12, fill=badge_bg)
        draw.text((bx1+pad_small, by1+int(pad_small*0.5)), badge, font=f_badge,
                  fill=badge_text, stroke_width=0, anchor=None)

    # --- title (top area) ---
    title = mapping.get("title") or ""
    if title:
        tx = pad
        ty = int(H*0.18) if badge else int(H*0.12)
        # outline για αναγνωσιμότητα
        draw.text((tx,ty), title, font=f_title, fill=pal["title_color"],
                  stroke_width=2, stroke_fill="#000000")

    # --- price block (bottom-left) ---
    price = mapping.get("price") or ""
    old_price = mapping.get("old_price") or ""
    px = pad
    py = int(H*0.72)

    if price:
        # current price
        draw.text((px,py), price, font=f_price, fill=pal["price_color"],
                  stroke_width=1, stroke_fill="#000000")
        pw,ph = _text_size(draw, price, f_price)
        # old price with strikethrough
        if old_price:
            ox = px
            oy = py + ph + pad_small//2
            draw.text((ox,oy), old_price, font=f_old, fill="#e5e7eb",
                      stroke_width=0)
            ow,oh = _text_size(draw, old_price, f_old)
            # strikethrough line
            line_y = oy + oh//2
            draw.line((ox, line_y, ox+ow, line_y), fill="#e5e7eb", width=max(2, oh//10))

    # --- CTA button (bottom-right) ---
    cta = mapping.get("cta") or ""
    if cta:
        tw,th = _text_size(draw, cta, f_cta)
        btn_pad_x = pad_small*2
        btn_pad_y = max(10, pad_small)
        bw = tw + btn_pad_x*2
        bh = th + btn_pad_y*2
        bx2 = W - pad
        bx1 = bx2 - bw
        by2 = H - pad
        by1 = by2 - bh
        cta_bg   = pal["cta_bg"]
        cta_text = pal.get("cta_text") or _auto_text_on(cta_bg)
        _draw_rounded_rect(draw, (bx1,by1,bx2,by2), radius=18, fill=cta_bg)
        draw.text((bx1+btn_pad_x, by1+btn_pad_y-2), cta, font=f_cta, fill=cta_text)

    # --- watermark (bottom-right, μικρό) ---
    if watermark:
        wm_text = mapping.get("watermark_text") or ""
        if wm_text:
            fw = _best_font(bold=False, size=int(H*0.025))
            tw,th = _text_size(draw, wm_text, fw)
            x = W - pad - tw
            y = H - pad - th - (bh if cta else 0) - pad_small
            draw.text((x,y), wm_text, font=fw, fill="rgba(255,255,255,180)")

    # meta
    meta = {"width": W, "height": H}
    return canvas, meta

def export_webp(img: Image.Image, quality: int = 92) -> bytes:
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=quality, method=6)
    return out.getvalue()
