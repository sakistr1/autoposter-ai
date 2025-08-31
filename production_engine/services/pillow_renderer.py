# services/pillow_renderer.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import os, time, io

# Προτεινόμενα paths (δεν γράφουμε αλλού)
STATIC_DIR = os.getenv("STATIC_DIR", "static")
OUT_DIR = os.path.join(STATIC_DIR, "generated")
FONTS_DIR = os.path.join("assets", "fonts")

# Προσπάθησε να βρεις γραμματοσειρά με ελληνικά· αλλιώς fallback.
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
    # Fallback: default PIL font (όχι ιδανικό για ελληνικά, αλλά δεν σπάει τίποτα)
    return ImageFont.load_default()

@dataclass
class RenderResult:
    out_path: str
    width: int
    height: int
    overlay_applied: bool

def _ensure_dirs():
    os.makedirs(OUT_DIR, exist_ok=True)

def _download_image_to_pil(url: str) -> Image.Image:
    """
    Κατεβάζει εικόνα μέσω stdlib (χωρίς extra deps). Αν αποτύχει, ρίχνει.
    """
    import urllib.request
    with urllib.request.urlopen(url, timeout=20) as r:
        data = r.read()
    return Image.open(io.BytesIO(data)).convert("RGBA")

def _draw_text_with_stroke(draw: ImageDraw.ImageDraw, xy: Tuple[int, int],
                           text: str, font: ImageFont.ImageFont,
                           fill=(255,255,255,255), stroke_width=0, stroke_fill=(0,0,0,255),
                           align="left", max_width: Optional[int]=None):
    # απλό wrap: κόβει λέξεις όταν ξεπερνά max_width
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
    """
    Minimal renderer:
    - Κατεβάζει base image
    - Προαιρετικά κάνει ελαφρύ blur στο background (αν είναι πολύ busy, για contrast)
    - Σχεδιάζει title/price/old_price/discount_badge/cta σε fixed θέσεις για 4:5
    - Σώζει prev_*.webp στο static/generated/
    """
    _ensure_dirs()

    base = _download_image_to_pil(image_url)

    # Canvas ratio (default 4:5 -> 1080x1350)
    if ratio in (None, "", "4:5"):
        W, H = 1080, 1350
    elif ratio == "1:1":
        W, H = 1080, 1080
    elif ratio in ("9:16", "9:16_story", "story"):
        W, H = 1080, 1920
    else:
        # άγνωστο ratio => fallback 4:5
        W, H = 1080, 1350

    # Fit base image to canvas (cover)
    bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    # cover: scale so that it covers the canvas
    scale = max(W / base.width, H / base.height)
    new_size = (int(base.width * scale), int(base.height * scale))
    im = base.resize(new_size, Image.LANCZOS)
    # center crop
    left = (im.width - W) // 2
    top = (im.height - H) // 2
    im = im.crop((left, top, left + W, top + H))

    # optional mild blur on background to improve text contrast
    # (δεν το κάνω πολύ δυνατό για να μη χαλάει)
    bg = im.filter(ImageFilter.GaussianBlur(radius=0.5))

    # compose final
    canvas = Image.alpha_composite(bg, Image.new("RGBA", (W, H), (0, 0, 0, 0)))

    draw = ImageDraw.Draw(canvas)

    # Defaults
    mp = mapping or {}
    title = str(mp.get("title") or "").strip()
    price = str(mp.get("price") or "").strip()
    old_price = str(mp.get("old_price") or "").strip()
    discount_badge = str(mp.get("discount_badge") or "").strip()
    cta = str(mp.get("cta") or "").strip()

    # Fonts
    title_font = _load_font(64)
    price_font = _load_font(56)
    small_font = _load_font(36)
    cta_font = _load_font(44)

    overlay_applied = False

    # semi-transparent overlay at bottom for readability
    overlay_h = 360
    overlay = Image.new("RGBA", (W, overlay_h), (0, 0, 0, 130))
    canvas.alpha_composite(overlay, (0, H - overlay_h))
    overlay_applied = True

    # Title (wrap)
    _draw_text_with_stroke(
        draw, (64, H - overlay_h + 32), title,
        font=title_font, fill=(255,255,255,255),
        stroke_width=2, stroke_fill=(0,0,0,180),
        max_width=W - 128
    )

    # Price + old price
    y_price = H - overlay_h + 160
    if price:
        _draw_text_with_stroke(draw, (64, y_price), price,
                               font=price_font, fill=(34,197,94,255),  # green-ish
                               stroke_width=2, stroke_fill=(0,0,0,160))
    if old_price:
        # draw old price with strike-through
        _draw_text_with_stroke(draw, (64, y_price + 64), old_price,
                               font=small_font, fill=(229,231,235,220),
                               stroke_width=2, stroke_fill=(0,0,0,140))
        # strike line
        bbox = draw.textbbox((64, y_price + 64), old_price, font=small_font)
        y_mid = (bbox[1] + bbox[3]) // 2
        draw.line((bbox[0], y_mid, bbox[2], y_mid), fill=(229,231,235,220), width=3)

    # Discount badge (top-left)
    if discount_badge:
        pad = 14
        txt_bbox = draw.textbbox((0,0), discount_badge, font=small_font)
        bw = (txt_bbox[2]-txt_bbox[0]) + pad*2
        bh = (txt_bbox[3]-txt_bbox[1]) + pad*2
        badge = Image.new("RGBA", (bw, bh), (239,68,68,220))  # red-ish
        canvas.alpha_composite(badge, (64, 64))
        draw.text((64+pad, 64+pad), discount_badge, font=small_font, fill=(255,255,255,255))

    # CTA button (bottom-right)
    if cta:
        btn_pad_x, btn_pad_y = 22, 12
        txt_bbox = draw.textbbox((0,0), cta, font=cta_font)
        bw = (txt_bbox[2]-txt_bbox[0]) + btn_pad_x*2
        bh = (txt_bbox[3]-txt_bbox[1]) + btn_pad_y*2
        bx = W - bw - 64
        by = H - bh - 64
        button = Image.new("RGBA", (bw, bh), (59,130,246,230))  # blue-ish
        # rounded rectangle (manual)
        button = ImageOps.expand(button, border=0)
        canvas.alpha_composite(button, (bx, by))
        draw.text((bx+btn_pad_x, by+btn_pad_y), cta, font=cta_font, fill=(255,255,255,255))

    # Watermark (bottom-left)
    if watermark:
        wm_text = "AUTOPOSTER-AI"
        wm_font = _load_font(22)
        draw.text((64, H - 32 - wm_font.size), wm_text, font=wm_font, fill=(255,255,255,140))

    # Save as WEBP
    ts = str(int(time.time() * 1000))
    out_name = f"prev_{ts}.webp"
    out_path = os.path.join(OUT_DIR, out_name)
    canvas = canvas.convert("RGB")  # webp without alpha to avoid glitches
    canvas.save(out_path, format="WEBP", quality=quality, method=6)

    return RenderResult(
        out_path=out_path,
        width=W,
        height=H,
        overlay_applied=overlay_applied,
    )
