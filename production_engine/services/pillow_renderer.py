# services/pillow_renderer.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import os, time, io

STATIC_DIR = os.getenv("STATIC_DIR", "static")
OUT_DIR = os.path.join(STATIC_DIR, "generated")
FONTS_DIR = os.path.join("assets", "fonts")

CANDIDATE_FONTS = [
    os.path.join(FONTS_DIR, "NotoSans-Regular.ttf"),
    os.path.join(FONTS_DIR, "Inter-Regular.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in CANDIDATE_FONTS:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()

def _hex_or_rgba(color: Optional[str], fallback: Tuple[int,int,int,int]) -> Tuple[int,int,int,int]:
    """
    Δέχεται "#rrggbb" ή "r,g,b,a" -> RGBA tuple. Αν είναι άκυρο/κενό → fallback.
    """
    if not color:
        return fallback
    s = str(color).strip()
    # rgba "r,g,b,a"
    if "," in s:
        try:
            parts = [int(x.strip()) for x in s.split(",")]
            if len(parts) == 4:
                r,g,b,a = parts
                return (max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)), max(0,min(255,a)))
        except Exception:
            return fallback
    # hex "#rrggbb"
    if s.startswith("#") and len(s) == 7:
        try:
            r = int(s[1:3], 16); g = int(s[3:5], 16); b = int(s[5:7], 16)
            return (r,g,b,255)
        except Exception:
            return fallback
    return fallback

@dataclass
class RenderResult:
    out_path: str
    width: int
    height: int
    overlay_applied: bool

def _ensure_dirs():
    os.makedirs(OUT_DIR, exist_ok=True)

def _download_image_to_pil(url: str) -> Image.Image:
    import urllib.request
    with urllib.request.urlopen(url, timeout=20) as r:
        data = r.read()
    return Image.open(io.BytesIO(data)).convert("RGBA")

def _draw_text_with_stroke(draw: ImageDraw.ImageDraw, xy: Tuple[int, int],
                           text: str, font: ImageFont.ImageFont,
                           fill=(255,255,255,255), stroke_width=0, stroke_fill=(0,0,0,255),
                           align="left", max_width: Optional[int]=None):
    if not text:
        return
    if max_width:
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            bbox = draw.textbbox((0,0), test, font=font, stroke_width=stroke_width)
            if bbox[2]-bbox[0] <= max_width:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        y = xy[1]
        for ln in lines:
            draw.text((xy[0], y), ln, font=font, fill=fill,
                      stroke_width=stroke_width, stroke_fill=stroke_fill, align=align)
            y += font.size + 8
    else:
        draw.text(xy, text, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill, align=align)

def render(
    image_url: str,
    mapping: Dict[str, Any] | None,
    ratio: str | None = None,
    watermark: bool | None = False,
    quality: int = 90,
) -> RenderResult:
    _ensure_dirs()
    base = _download_image_to_pil(image_url)

    # Canvas ratio
    r = (ratio or "").strip()
    if r in ("", "4:5"):
        W, H = 1080, 1350
    elif r == "1:1":
        W, H = 1080, 1080
    elif r in ("9:16", "9:16_story", "story"):
        W, H = 1080, 1920
    else:
        W, H = 1080, 1350

    # Fit base (cover) με ασφαλές fallback
    try:
        scale = max(W / max(1, base.width), H / max(1, base.height))
        new_size = (max(1, int(base.width * scale)), max(1, int(base.height * scale)))
        im = base.resize(new_size, Image.LANCZOS)
        left = max(0, (im.width - W) // 2)
        top = max(0, (im.height - H) // 2)
        right = min(im.width, left + W)
        bottom = min(im.height, top + H)
        if right - left != W or bottom - top != H:
            im = im.resize((W, H), Image.LANCZOS)
        else:
            im = im.crop((left, top, right, bottom))
    except Exception:
        im = base.resize((W, H), Image.LANCZOS)

    # ελαφρύ blur για contrast
    bg = im.filter(ImageFilter.GaussianBlur(radius=0.5))
    canvas = Image.alpha_composite(bg, Image.new("RGBA", (W, H), (0, 0, 0, 0)))
    draw = ImageDraw.Draw(canvas)

    mp = mapping or {}
    # κείμενα
    title = str(mp.get("title") or "").strip()
    price = str(mp.get("price") or "").strip()
    old_price = str(mp.get("old_price") or "").strip()
    discount_badge = str(mp.get("discount_badge") or "").strip()
    cta = str(mp.get("cta") or "").strip()
    # χρώματα (προαιρετικά)
    title_color = _hex_or_rgba(mp.get("title_color"), (255,255,255,255))
    price_color = _hex_or_rgba(mp.get("price_color"), (34,197,94,255))
    old_price_color = _hex_or_rgba(mp.get("old_price_color"), (229,231,235,220))
    badge_bg = _hex_or_rgba(mp.get("badge_bg"), (239,68,68,220))
    badge_text = _hex_or_rgba(mp.get("badge_text"), (255,255,255,255))
    cta_bg = _hex_or_rgba(mp.get("cta_bg"), (59,130,246,230))
    cta_text = _hex_or_rgba(mp.get("cta_text"), (255,255,255,255))
    overlay_rgba = _hex_or_rgba(mp.get("overlay_rgba"), (0,0,0,130))

    # Fonts
    title_font = _load_font(64)
    price_font = _load_font(56)
    small_font = _load_font(36)
    cta_font = _load_font(44)

    overlay_applied = False

    # overlay band
    overlay_h = 360
    overlay = Image.new("RGBA", (W, overlay_h), overlay_rgba)
    canvas.alpha_composite(overlay, (0, H - overlay_h))
    overlay_applied = True

    # Title
    _draw_text_with_stroke(
        draw, (64, H - overlay_h + 32), title,
        font=title_font, fill=title_color,
        stroke_width=2, stroke_fill=(0,0,0,180),
        max_width=W - 128
    )

    # Price + old price
    y_price = H - overlay_h + 160
    if price:
        _draw_text_with_stroke(draw, (64, y_price), price,
                               font=price_font, fill=price_color,
                               stroke_width=2, stroke_fill=(0,0,0,160))
    if old_price:
        _draw_text_with_stroke(draw, (64, y_price + 64), old_price,
                               font=small_font, fill=old_price_color,
                               stroke_width=2, stroke_fill=(0,0,0,140))
        bbox = draw.textbbox((64, y_price + 64), old_price, font=small_font)
        y_mid = (bbox[1] + bbox[3]) // 2
        # η γραμμή χρησιμοποιεί το ίδιο χρώμα με το κείμενο του old price
        draw.line((bbox[0], y_mid, bbox[2], y_mid), fill=old_price_color, width=3)

    # Discount badge
    if discount_badge:
        pad = 14
        txt_bbox = draw.textbbox((0,0), discount_badge, font=small_font)
        bw = (txt_bbox[2]-txt_bbox[0]) + pad*2
        bh = (txt_bbox[3]-txt_bbox[1]) + pad*2
        badge = Image.new("RGBA", (bw, bh), badge_bg)
        canvas.alpha_composite(badge, (64, 64))
        draw.text((64+pad, 64+pad), discount_badge, font=small_font, fill=badge_text)

    # CTA button
    if cta:
        btn_pad_x, btn_pad_y = 22, 12
        txt_bbox = draw.textbbox((0,0), cta, font=cta_font)
        bw = (txt_bbox[2]-txt_bbox[0]) + btn_pad_x*2
        bh = (txt_bbox[3]-txt_bbox[1]) + btn_pad_y*2
        bx = W - bw - 64
        by = H - bh - 64
        button = Image.new("RGBA", (bw, bh), cta_bg)
        button = ImageOps.expand(button, border=0)
        canvas.alpha_composite(button, (bx, by))
        draw.text((bx+btn_pad_x, by+btn_pad_y), cta, font=cta_font, fill=cta_text)

    # Watermark
    if watermark:
        wm_text = "AUTOPOSTER-AI"
        wm_font = _load_font(22)
        draw.text((64, H - 32 - wm_font.size), wm_text, font=wm_font, fill=(255,255,255,140))

    # Save WEBP
    ts = str(int(time.time() * 1000))
    out_name = f"prev_{ts}.webp"
    out_path = os.path.join(OUT_DIR, out_name)
    canvas = canvas.convert("RGB")
    canvas.save(out_path, format="WEBP", quality=quality, method=6)

    return RenderResult(out_path=out_path, width=W, height=H, overlay_applied=overlay_applied)
