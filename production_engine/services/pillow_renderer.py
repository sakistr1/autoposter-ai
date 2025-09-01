from __future__ import annotations
from typing import Any, Dict, Optional
from types import SimpleNamespace
from pathlib import Path
import time, os
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

STATIC_DIR = Path("static")
GENERATED_DIR = STATIC_DIR / "generated"
DEFAULT_FONT = None  # θα πέσουμε σε load_default()

def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _to_local(path_or_url: str) -> Path:
    s = (path_or_url or "").strip()
    if not s:
        raise ValueError("empty path")
    if s.startswith("/static/"):
        return Path(s.lstrip("/"))
    if s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        if parsed.path.startswith("/static/"):
            return Path(parsed.path.lstrip("/"))
        raise ValueError("renderer expects local /static path, not remote url")
    if s.startswith("static/"):
        return Path(s)
    raise ValueError("unsupported image path – must be under /static")

def _safe_area_for_ratio(w: int, h: int, ratio: str) -> Dict[str, int]:
    r = (ratio or "4:5").strip()
    if r == "1:1":
        return {"x": 0, "y": 0, "w": w, "h": h}
    if r == "4:5":
        used_h = int(h * 0.80)
        return {"x": 0, "y": 0, "w": w, "h": used_h}
    if r == "9:16":
        used_h = int(h * 0.75)
        return {"x": 0, "y": 0, "w": w, "h": used_h}
    used_h = int(h * 0.80)
    return {"x": 0, "y": 0, "w": w, "h": used_h}

def _load_font(sz: int):
    global DEFAULT_FONT
    try:
        fpath = Path("assets/fonts/NotoSans-Regular.ttf")
        if fpath.exists():
            return ImageFont.truetype(str(fpath), sz)
    except Exception:
        pass
    try:
        if DEFAULT_FONT is None:
            DEFAULT_FONT = ImageFont.load_default()
        return DEFAULT_FONT
    except Exception:
        return None

def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    r = int(radius)
    draw.rounded_rectangle([x0, y0, x1, y1], r, fill=fill)

def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    """Return (w,h) for text using safe Pillow API."""
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l, b - t
    except Exception:
        try:
            return draw.textsize(text, font=font)
        except Exception:
            sz = getattr(font, "size", 24)
            return max(1, int(sz * 0.6 * len(text))), max(1, sz)

def render(
    *,
    template_id: Optional[int] = None,
    image_url: str,
    mapping: Optional[Dict[str, Any]] = None,
    ratio: str = "4:5",
    meta: Optional[Dict[str, Any]] = None,
    output_format: str = "jpg",
    quality: int = 90,
    overlay: Optional[int] = None,
    watermark: Optional[bool] = None,
    **kwargs: Any,
) -> SimpleNamespace:
    mp = mapping or {}
    title = (mp.get("title") or "").strip()
    price = (mp.get("price") or mp.get("price_text") or "").strip()
    old_price = (mp.get("old_price") or mp.get("old_price_text") or "").strip()
    cta_text = (mp.get("cta") or mp.get("cta_text") or "").strip()
    logo_path = (mp.get("logo_url") or mp.get("logo_path") or "").strip()
    want_badge = bool(mp.get("discount_badge", True))

    src = _to_local(image_url)
    if not src.exists():
        raise FileNotFoundError(f"image not found: {src}")
    with Image.open(src) as im:
        im = im.convert("RGBA")
        w, h = im.size

        safe_area = _safe_area_for_ratio(w, h, ratio)
        slots_used: Dict[str, Dict[str, int]] = {}

        draw = ImageDraw.Draw(im)
        font_title = _load_font(max(32, int(w * 0.04)))
        font_price = _load_font(max(28, int(w * 0.035)))
        font_cta = _load_font(max(28, int(w * 0.032)))

        # Logo
        logo_applied = False
        if logo_path:
            try:
                lp = _to_local(logo_path)
                if lp.exists():
                    with Image.open(lp) as lg:
                        lg = lg.convert("RGBA")
                        box = int(min(w, h) * 0.11)
                        lg.thumbnail((box, box))
                        pad = int(w * 0.035)
                        x = w - pad - lg.width
                        y = pad
                        im.alpha_composite(lg, (x, y))
                        slots_used["logo"] = {"x": x, "y": y, "w": lg.width, "h": lg.height}
                        logo_applied = True
            except Exception:
                logo_applied = False

        # Discount badge
        discount_badge_applied = False
        if want_badge and old_price and price:
            try:
                pad = int(w * 0.035)
                bw = int(w * 0.25)
                bh = int(h * 0.08)
                x0, y0 = pad, pad
                x1, y1 = x0 + bw, y0 + bh
                _draw_rounded_rect(draw, (x0, y0, x1, y1), radius=int(bh*0.25), fill=(220, 38, 38, 220))
                txt = f"-{_discount_percent(old_price, price)}%"
                tw, th = _measure(draw, txt, font_price)
                tx = x0 + (bw - tw)//2
                ty = y0 + (bh - th)//2
                draw.text((tx, ty), txt, fill=(255,255,255,255), font=font_price)
                slots_used["badge"] = {"x": x0, "y": y0, "w": bw, "h": bh}
                discount_badge_applied = True
            except Exception:
                discount_badge_applied = False

        # CTA
        cta_applied = False
        if cta_text:
            try:
                pad = int(w * 0.035)
                bw = int(w * 0.38)
                bh = int(h * 0.09)
                x0 = pad
                y0 = min(safe_area["y"] + safe_area["h"], h) - pad - bh
                x1, y1 = x0 + bw, y0 + bh
                _draw_rounded_rect(draw, (x0, y0, x1, y1), radius=int(bh*0.35), fill=(34, 197, 94, 235))
                tw, th = _measure(draw, cta_text[:20], font_cta)
                tx = x0 + (bw - tw)//2
                ty = y0 + (bh - th)//2
                draw.text((tx, ty), cta_text[:20], fill=(255,255,255,255), font=font_cta)
                slots_used["cta"] = {"x": x0, "y": y0, "w": bw, "h": bh}
                cta_applied = True
            except Exception:
                cta_applied = False

        # Price strip
        overlay_applied = False
        if price or title:
            try:
                pad = int(w * 0.035)
                bw = int(w * 0.42)
                bh = int(h * 0.15)
                x1 = w - pad
                y1 = min(safe_area["y"] + safe_area["h"], h) - pad
                x0 = x1 - bw
                y0 = y1 - bh
                _draw_rounded_rect(draw, (x0, y0, x1, y1), radius=int(bh*0.15), fill=(0,0,0,170))
                if title:
                    draw.text((x0+pad, y0+pad), title[:40], fill=(255,255,255,255), font=font_title)
                if price:
                    draw.text((x0+pad, y0+pad+int(bh*0.45)), f"{price}", fill=(255,255,255,255), font=font_price)
                overlay_applied = True
                slots_used["price_strip"] = {"x": x0, "y": y0, "w": bw, "h": bh}
            except Exception:
                overlay_applied = overlay_applied or False

        # Save
        out_name = f"prev_{int(time.time()*1000)}.jpg" if output_format.lower() in {"jpg","jpeg"} else f"prev_{int(time.time()*1000)}.webp"
        dst = GENERATED_DIR / out_name
        _ensure_dir(dst)
        out = im.convert("RGB")
        if dst.suffix.lower() == ".webp":
            out.save(dst, format="WEBP", quality=quality, method=6)
        else:
            out.save(dst, format="JPEG", quality=quality)

        return SimpleNamespace(
            out_path=str(dst),
            overlay_applied=bool(overlay_applied),
            logo_applied=bool(logo_applied),
            discount_badge_applied=bool(discount_badge_applied),
            cta_applied=bool(cta_applied),
            slots_used=slots_used,
            safe_area=_safe_area_for_ratio(w, h, ratio),
            width=w,
            height=h,
            format=dst.suffix.lower().lstrip("."),
            quality_used=quality,
        )

def _discount_percent(old_price: str, new_price: str) -> int:
    def _to_num(s: str) -> float:
        s = s.replace("€","").replace(",",".").strip()
        try:
            return float(s)
        except Exception:
            return 0.0
    old_v = _to_num(old_price)
    new_v = _to_num(new_price)
    if old_v <= 0 or new_v <= 0 or new_v >= old_v:
        return 0
    return int(round((1 - new_v/old_v) * 100))
