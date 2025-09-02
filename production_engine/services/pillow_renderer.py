from __future__ import annotations
from typing import Any, Dict, Optional, List, Tuple
from types import SimpleNamespace
from pathlib import Path
import time
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont, ImageFilter

STATIC_DIR = Path("static")
GENERATED_DIR = STATIC_DIR / "generated"
DEFAULT_FONT = None

# -----------------------------
# Helpers (paths / io / fonts)
# -----------------------------
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

def _load_font(sz: int):
    """
    Προσπαθεί πρώτα με NotoSans (για σωστά ελληνικά). Αλλιώς default.
    """
    global DEFAULT_FONT
    try:
        fpath = Path("assets/fonts/NotoSans-Regular.ttf")
        if fpath.exists():
            return ImageFont.truetype(str(fpath), sz)
    except Exception:
        pass
    if DEFAULT_FONT is None:
        DEFAULT_FONT = ImageFont.load_default()
    return DEFAULT_FONT

# -----------------------------
# Safe-area ανά ratio
# -----------------------------
def _safe_area_for_ratio(w: int, h: int, ratio: str) -> Dict[str, int]:
    r = (ratio or "4:5").strip()
    if r == "1:1":
        used_h = int(h * 0.85)
    elif r == "4:5":
        used_h = int(h * 0.82)
    elif r == "9:16":
        used_h = int(h * 0.78)
    else:
        used_h = int(h * 0.82)
    return {"x": 0, "y": 0, "w": w, "h": used_h}

# -----------------------------
# Drawing utilities (measure / wrap / fit / text)
# -----------------------------
def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font, stroke_width=0)
        return r - l, b - t
    except Exception:
        # Fallback
        try:
            return draw.textsize(text, font=font)
        except Exception:
            sz = getattr(font, "size", 24)
            return max(1, int(sz * 0.6 * len(text))), max(1, sz)

def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int) -> List[str]:
    """
    Απλό word wrapping (με fallback σε char wrap) ώστε να μη σπάει εκτός πλαισίου.
    """
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    cur: List[str] = []
    for w in words:
        test = (" ".join(cur + [w])).strip()
        tw, _ = _measure(draw, test, font)
        if tw <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))

    # αν ακόμη ξεχειλώνει, κόψε χαρακτήρες και βάλε «…»
    out: List[str] = []
    for ln in lines[:max_lines]:
        while ln and _measure(draw, ln, font)[0] > max_w:
            ln = ln[:-1]
        if not ln:
            continue
        if _measure(draw, ln + "…", font)[0] <= max_w:
            ln = ln + "…"
        out.append(ln)
    return out[:max_lines]

def _shrink_to_fit(draw: ImageDraw.ImageDraw, text: str, font_start_px: int, max_w: int, max_h: int, min_px: int = 16) -> ImageFont.FreeTypeFont:
    """
    Κατεβάζει μέγεθος γραμματοσειράς μέχρι να χωράει text σε (max_w x max_h).
    """
    px = font_start_px
    while px >= min_px:
        f = _load_font(px)
        tw, th = _measure(draw, text, f)
        if tw <= max_w and th <= max_h:
            return f
        px -= 1
    return _load_font(min_px)

def _draw_text(draw: ImageDraw.ImageDraw, xy: Tuple[int, int], text: str, font, fill=(255, 255, 255, 255)):
    """
    Κείμενο με λεπτό stroke + ελαφρύ shadow για contrast.
    """
    x, y = xy
    # Shadow
    shadow_off = 1
    draw.text((x + shadow_off, y + shadow_off), text, font=font, fill=(0, 0, 0, 140))
    # Stroke
    draw.text((x, y), text, font=font, fill=fill, stroke_width=1, stroke_fill=(0, 0, 0, 180))

def _rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], int(radius), fill=fill)

# -----------------------------
# Discount utils
# -----------------------------
def _discount_percent(old_price: str, new_price: str) -> int:
    def _to_num(s: str) -> float:
        s = s.replace("€", "").replace(",", ".").strip()
        try:
            return float(s)
        except Exception:
            return 0.0
    o = _to_num(old_price)
    n = _to_num(new_price)
    if o <= 0 or n <= 0 or n >= o:
        return 0
    return int(round((1 - n / o) * 100))

# -----------------------------
# MAIN render()
# -----------------------------
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

    # image path
    try:
        src = _to_local(image_url)
    except Exception as e:
        return SimpleNamespace(
            out_path=None, overlay_applied=False, logo_applied=False,
            discount_badge_applied=False, cta_applied=False,
            slots_used={}, safe_area={}, width=0, height=0,
            format=output_format, quality_used=quality,
            error=f"invalid image path: {image_url} ({e})"
        )
    if not src.exists():
        return SimpleNamespace(
            out_path=None, overlay_applied=False, logo_applied=False,
            discount_badge_applied=False, cta_applied=False,
            slots_used={}, safe_area={}, width=0, height=0,
            format=output_format, quality_used=quality,
            error=f"image not found: {src}"
        )

    with Image.open(src) as im:
        im = im.convert("RGBA")
        w, h = im.size
        draw = ImageDraw.Draw(im)

        safe_area = _safe_area_for_ratio(w, h, ratio)
        slots_used: Dict[str, Dict[str, int]] = {}

        # Base fonts (θα γίνει shrink-to-fit όπου χρειάζεται)
        font_title_base = _load_font(max(34, int(w * 0.048)))
        font_price_base = _load_font(max(30, int(w * 0.040)))
        font_cta_base   = _load_font(max(28, int(w * 0.038)))

        # 1) Logo επάνω δεξιά
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

        # 2) Badge έκπτωσης επάνω αριστερά
        discount_badge_applied = False
        if want_badge and old_price and price:
            try:
                pad = int(w * 0.035)
                bw = int(w * 0.26)
                bh = int(h * 0.085)
                x0, y0 = pad, pad
                x1, y1 = x0 + bw, y0 + bh
                _rounded_rect(draw, (x0, y0, x1, y1), radius=int(bh * 0.28), fill=(220, 38, 38, 230))
                pct = _discount_percent(old_price, price)
                txt = f"-{pct}%"
                # μεγιστοποίηση γραμματοσειράς μέσα στο badge
                f = _shrink_to_fit(draw, txt, font_price_base.size, bw - int(bw * 0.18), bh - int(bh * 0.3), min_px=18)
                tw, th = _measure(draw, txt, f)
                tx = x0 + (bw - tw) // 2
                ty = y0 + (bh - th) // 2
                _draw_text(draw, (tx, ty), txt, f, fill=(255, 255, 255, 255))
                slots_used["badge"] = {"x": x0, "y": y0, "w": bw, "h": bh}
                discount_badge_applied = True
            except Exception:
                discount_badge_applied = False

        # 3) CTA κάτω αριστερά, μέσα στο safe-area
        cta_applied = False
        if cta_text:
            try:
                pad = int(w * 0.035)
                bw = int(w * 0.42)
                bh = int(h * 0.10)
                x0 = pad
                y0 = min(safe_area["y"] + safe_area["h"], h) - pad - bh
                x1, y1 = x0 + bw, y0 + bh
                _rounded_rect(draw, (x0, y0, x1, y1), radius=int(bh * 0.40), fill=(34, 197, 94, 240))
                # fit text
                f = _shrink_to_fit(draw, cta_text, font_cta_base.size, bw - int(bw * 0.2), bh - int(bh * 0.38), min_px=18)
                tw, th = _measure(draw, cta_text, f)
                tx = x0 + (bw - tw) // 2
                ty = y0 + (bh - th) // 2
                _draw_text(draw, (tx, ty), cta_text, f, fill=(255, 255, 255, 255))
                slots_used["cta"] = {"x": x0, "y": y0, "w": bw, "h": bh}
                cta_applied = True
            except Exception:
                cta_applied = False

        # 4) Price strip κάτω δεξιά (μαύρο πάνελ)
        overlay_applied = False
        if title or price:
            try:
                pad = int(w * 0.035)
                bw = int(w * 0.46)
                bh = int(h * 0.17)
                x1 = w - pad
                y1 = min(safe_area["y"] + safe_area["h"], h) - pad
                x0 = x1 - bw
                y0 = y1 - bh

                # ημιδιάφανο μαύρο πάνελ
                _rounded_rect(draw, (x0, y0, x1, y1), radius=int(bh * 0.20), fill=(0, 0, 0, 180))

                inner_x = x0 + int(bw * 0.08)
                inner_y = y0 + int(bh * 0.15)
                inner_w = bw - int(bw * 0.16)

                # Τίτλος: μέχρι 2 γραμμές με wrapping
                if title:
                    title_font = _load_font(font_title_base.size)
                    lines = _wrap_lines(draw, title, title_font, inner_w, max_lines=2)
                    # Αν οι δυο γραμμές δεν χωράνε σε ύψος, ρίξε μέγεθος
                    max_title_h = int(bh * 0.55)
                    while True:
                        total_h = 0
                        line_hs: List[int] = []
                        for ln in lines:
                            _, lh = _measure(draw, ln, title_font)
                            line_hs.append(lh)
                            total_h += lh
                        if total_h <= max_title_h or title_font.size <= 18:
                            break
                        title_font = _load_font(title_font.size - 1)

                    cy = inner_y
                    for ln in lines:
                        _draw_text(draw, (inner_x, cy), ln, title_font)
                        cy += _measure(draw, ln, title_font)[1]

                # Τιμή: πιο μεγάλη από τον τίτλο, κάτω μέρος του πάνελ
                if price:
                    price_area_h = int(bh * 0.36)
                    price_font = _shrink_to_fit(
                        draw, price, max(font_price_base.size, title and font_price_base.size + 2 or font_price_base.size),
                        inner_w, price_area_h, min_px=18
                    )
                    # στοίχιση κάτω αριστερά
                    px = inner_x
                    py = y1 - int(bh * 0.12) - _measure(draw, price, price_font)[1]
                    _draw_text(draw, (px, py), price, price_font)

                overlay_applied = True
                slots_used["price_strip"] = {"x": x0, "y": y0, "w": bw, "h": bh}
            except Exception:
                overlay_applied = overlay_applied or False

        # Αποθήκευση
        ts = int(time.time() * 1000)
        out_name = f"prev_{ts}.webp" if output_format.lower() == "webp" else f"prev_{ts}.jpg"
        dst = GENERATED_DIR / out_name
        _ensure_dir(dst)
        rgb = im.convert("RGB")
        if dst.suffix.lower() == ".webp":
            rgb.save(dst, format="WEBP", quality=quality, method=6)
        else:
            rgb.save(dst, format="JPEG", quality=quality)

        return SimpleNamespace(
            out_path=str(dst),
            overlay_applied=bool(overlay_applied),
            logo_applied=bool(logo_applied),
            discount_badge_applied=bool(discount_badge_applied),
            cta_applied=bool(cta_applied),
            slots_used=slots_used,
            safe_area=_safe_area_for_ratio(w, h, ratio),
            width=w, height=h,
            format=dst.suffix.lower().lstrip("."),
            quality_used=quality,
        )
