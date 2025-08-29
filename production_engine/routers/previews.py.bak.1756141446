# production_engine/routers/previews.py
from datetime import datetime
import os
import json
from typing import List, Optional
from io import BytesIO

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field, RootModel
from sqlalchemy import insert, select, desc
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urljoin, urlparse

import httpx
import logging

from production_engine.engine_database import engine, committed_posts_table
from production_engine.engine_database import pe_templates_table

logger = logging.getLogger(__name__)
router = APIRouter()

# ======================
# Models
# ======================
class TextFields(RootModel[dict]):
    pass

class RenderRequest(BaseModel):
    template_id: Optional[int] = None
    product_id: Optional[int] = None
    post_type: str = "image"
    mode: Optional[str] = None
    ratio: Optional[str] = None   # '4:5' | '1:1' | '9:16'

    # περιεχόμενο
    title: Optional[str] = None
    price: Optional[str] = None
    text_fields: Optional[dict] = None  # {"title","price","cta"}

    brand_logo_url: Optional[str] = None
    image_url: Optional[str] = None        # http(s) ή /static/…
    extra_images: List[str] = []

class CommitRequest(BaseModel):
    preview_id: Optional[str] = None
    preview_url: Optional[str] = None
    urls: Optional[List[str]] = None

# ======================
# Paths / Fonts
# ======================
STATIC_ROOT   = os.path.join("static")
GENERATED_DIR = os.path.join(STATIC_ROOT, "generated")
FONTS_DIR     = os.path.join("production_engine", "assets", "fonts")
os.makedirs(GENERATED_DIR, exist_ok=True)

# ======================
# Helpers
# ======================
def _load_template_spec(template_id: int) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(pe_templates_table.c.id, pe_templates_table.c.spec_json)
            .where(pe_templates_table.c.id == template_id)
        ).mappings().first()
    if not row:
        return None
    try:
        return json.loads(row["spec_json"]) if row["spec_json"] else None
    except Exception:
        return None

def _is_allowed_image_url(u: str) -> bool:
    """Whitelist: μόνο http/https ή /static/..."""
    if not isinstance(u, str) or not u.strip():
        return False
    s = u.strip()
    if s.startswith("/static/"):
        return True
    try:
        p = urlparse(s)
    except Exception:
        return False
    return p.scheme in ("http", "https")

def _open_image_any(src: str) -> Image.Image:
    """
    Ανοίγει εικόνα από http(s) ή /static/... Μπλοκάρει οτιδήποτε άλλο (π.χ. /etc/hosts).
    Περιέχει guard για path traversal με realpath.
    """
    if not isinstance(src, str) or not src.strip():
        raise FileNotFoundError("empty image src")
    s = src.strip()

    # --- WHITELIST GUARD ---
    if not _is_allowed_image_url(s):
        # Δεν επιτρέπουμε πρόσβαση εκτός /static ή χωρίς http(s)
        raise FileNotFoundError("disallowed image path")

    if s.startswith("http://") or s.startswith("https://"):
        headers = {"User-Agent": "AutoposterAI/1.0 (+httpx)"}
        try:
            r = httpx.get(s, timeout=15, headers=headers, follow_redirects=True)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGBA")
        except Exception as e1:
            logger.warning("HTTP image fetch failed (verify=True): %s -> %s", s, e1)
            try:
                r = httpx.get(s, timeout=15, headers=headers, follow_redirects=True, verify=False)
                r.raise_for_status()
                return Image.open(BytesIO(r.content)).convert("RGBA")
            except Exception as e2:
                logger.error("HTTP image fetch failed (verify=False): %s -> %s", s, e2)
                raise FileNotFoundError(f"cannot fetch {s}: {e2}")

    # Από εδώ και κάτω μόνο για /static/...
    if s.startswith("/static/"):
        rel = s[len("/static/"):]
        # ===== Harden: confine μέσα στο STATIC_ROOT με realpath =====
        static_root_abs = os.path.realpath(STATIC_ROOT)
        cand1 = os.path.realpath(os.path.join(STATIC_ROOT, rel))
        if not (cand1 == static_root_abs or cand1.startswith(static_root_abs + os.sep)):
            raise FileNotFoundError("outside static")

        if os.path.exists(cand1):
            return Image.open(cand1).convert("RGBA")

        # Επιτρέπουμε και assets μέσα στο production_engine/static με ίδιο guard
        pe_static_root = os.path.join("production_engine", "static")
        pe_static_abs  = os.path.realpath(pe_static_root)
        cand2 = os.path.realpath(os.path.join(pe_static_root, rel))
        if not (cand2 == pe_static_abs or cand2.startswith(pe_static_abs + os.sep)):
            raise FileNotFoundError("outside static(pe)")

        if os.path.exists(cand2):
            return Image.open(cand2).convert("RGBA")

        raise FileNotFoundError(cand1)

    # Αν φτάσεις εδώ, κάτι ξέφυγε από το guard (δεν θα έπρεπε)
    raise FileNotFoundError(s)

def _paste_fit(img: Image.Image, slot: dict) -> Image.Image:
    fit = slot.get("fit", "contain")
    x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
    target = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ratio = max(w / img.width, h / img.height) if fit == "cover" else min(w / img.width, h / img.height)
    new_w = max(1, int(img.width * ratio))
    new_h = max(1, int(img.height * ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    offset_x = max(0, (w - new_w) // 2)
    offset_y = max(0, (h - new_h) // 2)
    target.alpha_composite(resized, (offset_x, offset_y))
    return target

def _wrap_text_by_width(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw):
    lines = []
    for paragraph in str(text or "").split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split(" ")
        line = ""
        for w in words:
            candidate = (line + " " + w).strip()
            bb = draw.textbbox((0, 0), candidate, font=font)
            if (bb[2] - bb[0]) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line); line = w
                else:
                    acc = ""
                    for ch in w:
                        trial = acc + ch
                        bb2 = draw.textbbox((0, 0), trial, font=font)
                        if (bb2[2] - bb2[0]) > max_width and acc:
                            lines.append(acc); acc = ch
                        else:
                            acc = trial
                    if acc: line = acc
        if line: lines.append(line)
    return lines

def _draw_text(draw: ImageDraw.ImageDraw, slot: dict, text: str, font_dir: str):
    x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
    align = slot.get("align", "left")
    size = int(slot.get("font_size", 40))
    color = slot.get("color", "#ffffff")
    bold = bool(slot.get("bold", False))
    stroke_w = int(slot.get("stroke_width", 3))
    stroke_c = slot.get("stroke_color", "#0a0a0a")
    line_spacing = float(slot.get("line_spacing", 1.15))

    font_path = os.path.join(font_dir, "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf")
    try:
        font = ImageFont.truetype(font_path, size=size)
    except Exception:
        font = ImageFont.load_default()

    lines = _wrap_text_by_width(text or "", font, w, draw)
    ref = draw.textbbox((0, 0), "Ag", font=font)
    line_h = max(1, int((ref[3] - ref[1]) * line_spacing))
    cur_y = y
    for line in lines:
        if cur_y > y + h - line_h: break
        bb = draw.textbbox((0, 0), line, font=font)
        w_px = bb[2] - bb[0]
        tx = x + (w - w_px)//2 if align == "center" else (x + (w - w_px) if align == "right" else x)
        if stroke_w > 0:
            draw.text((tx, cur_y), line, font=font, fill=color, stroke_width=stroke_w, stroke_fill=stroke_c)
        else:
            draw.text((tx, cur_y), line, font=font, fill=color)
        cur_y += line_h

def _canvas_from_ratio(ratio: Optional[str]) -> tuple[int, int]:
    r = (ratio or "").strip()
    if r == "4:5": return (1080, 1350)
    if r == "9:16": return (1080, 1920)
    return (1080, 1080)

def _local_static_path_from_url(u: str) -> Optional[str]:
    """Αν το URL δείχνει σε /static/… στο ίδιο app, επέστρεψε local path, αλλιώς None."""
    try:
        p = urlparse(u)
        path = p.path if p.scheme else u
    except Exception:
        path = u
    if isinstance(path, str) and path.startswith("/static/"):
        rel = path[len("/static/"):]
        return os.path.join(STATIC_ROOT, rel)
    return None

# ======================
# Routes
# ======================
@router.post("/previews/render")
def render_image(payload: RenderRequest):
    canvas_w, canvas_h = _canvas_from_ratio(payload.ratio)
    base = Image.new("RGBA", (canvas_w, canvas_h), (16, 22, 28, 255))

    spec = _load_template_spec(payload.template_id) if payload.template_id else None

    if spec and "slots" in spec:
        if spec.get("canvas_w") and spec.get("canvas_h"):
            canvas_w = int(spec["canvas_w"]); canvas_h = int(spec["canvas_h"])
            base = Image.new("RGBA", (canvas_w, canvas_h), (16, 22, 28, 255))

        if spec.get("background"):
            try:
                bg_src = spec["background"]
                if not _is_allowed_image_url(bg_src):
                    raise FileNotFoundError("disallowed image path")
                bg = _open_image_any(bg_src)
                base.alpha_composite(_paste_fit(bg, {"x": 0, "y": 0, "w": canvas_w, "h": canvas_h, "fit": "cover"}), (0, 0))
            except Exception as e:
                logger.warning("background load failed: %s", e)

        draw = ImageDraw.Draw(base)
        font_dir = FONTS_DIR

        extra_map = {f"extra{idx}": p for idx, p in enumerate(payload.extra_images, start=1)}

        for slot in spec.get("slots", []):
            kind = slot.get("kind")
            if kind in ("image", "logo"):
                src = None
                if kind == "logo" and payload.brand_logo_url:
                    src = payload.brand_logo_url
                elif kind == "image":
                    src_key = slot.get("source")
                    if src_key == "product" and payload.image_url:
                        src = payload.image_url
                    elif src_key and src_key in extra_map:
                        src = extra_map[src_key]
                if src:
                    try:
                        if not _is_allowed_image_url(src):
                            raise FileNotFoundError("disallowed image path")
                        img = _open_image_any(src)
                        piece = _paste_fit(img, slot)
                        base.alpha_composite(piece, (slot["x"], slot["y"]))
                    except Exception as e:
                        logger.warning("slot image failed: %s", e)
            elif kind == "text":
                text_key = slot.get("text_key")
                tf = payload.text_fields or {}
                if text_key == "title":
                    val = str(tf.get("title") or payload.title or "")
                elif text_key == "price":
                    val = str(tf.get("price") or payload.price or "")
                else:
                    val = str(tf.get(text_key, "") if text_key else "")
                _draw_text(draw, slot, val, font_dir)

    else:
        draw = ImageDraw.Draw(base)
        font_dir = FONTS_DIR

        if payload.image_url:
            try:
                if not _is_allowed_image_url(payload.image_url):
                    raise FileNotFoundError("disallowed image path")
                prod = _open_image_any(payload.image_url)
                piece = _paste_fit(prod, {"x": 0, "y": 0, "w": canvas_w, "h": canvas_h, "fit": "cover"})
                base.alpha_composite(piece, (0, 0))
            except Exception as e:
                logger.error("product image load failed: %s", e)

        overlay = Image.new("RGBA", (canvas_w, canvas_h), (6, 10, 14, 120))
        base.alpha_composite(overlay, (0, 0))

        if payload.brand_logo_url:
            try:
                if not _is_allowed_image_url(payload.brand_logo_url):
                    raise FileNotFoundError("disallowed image path")
                logo = _open_image_any(payload.brand_logo_url)
                slot = {"x": 40, "y": 40, "w": 200, "h": 200, "fit": "contain"}
                base.alpha_composite(_paste_fit(logo, slot), (slot["x"], slot["y"]))
            except Exception as e:
                logger.warning("logo load failed: %s", e)

        tf = payload.text_fields or {}
        title = str(tf.get("title") or payload.title or (f"Προϊόν #{payload.product_id}" if payload.product_id else "Προϊόν"))
        price = str(tf.get("price") or payload.price or "")
        cta   = str(tf.get("cta")   or "Αγόρασε τώρα")

        _draw_text(draw, {"x": 40, "y": 280, "w": canvas_w - 80, "h": int(canvas_h * 0.5),
                          "font_size": 72, "bold": True, "align": "left", "color": "#ffffff",
                          "stroke_width": 4, "stroke_color": "#000000"}, title, font_dir)
        if price:
            _draw_text(draw, {"x": 40, "y": 280 + 72 + 24, "w": canvas_w - 80, "h": 120,
                              "font_size": 60, "bold": True, "align": "left", "color": "#22c55e",
                              "stroke_width": 3, "stroke_color": "#000000"}, price, font_dir)
        _draw_text(draw, {"x": 40, "y": canvas_h - 140, "w": canvas_w - 80, "h": 100,
                          "font_size": 42, "bold": False, "align": "left", "color": "#e5e7eb",
                          "stroke_width": 2, "stroke_color": "#000000"}, cta, font_dir)

    preview_id = f"prev_{int(datetime.utcnow().timestamp()*1000)}"
    out_path = os.path.join(GENERATED_DIR, f"{preview_id}.png")
    base.convert("RGB").save(out_path, "PNG")
    return {"preview_id": preview_id, "preview_url": f"/static/generated/{preview_id}.png"}

# ======================
# Credits guard
# ======================
def credits_guard_should_skip() -> bool:
    return os.getenv("DISABLE_CREDITS_GUARD", "0").lower() in ("1","true","yes")

async def debit_one_credit(authorization: Optional[str]) -> None:
    if credits_guard_should_skip():
        return
    debit_url = os.getenv("CREDITS_DEBIT_URL", "http://localhost:8000/me/use-credit")
    headers = {}
    if authorization: headers["Authorization"] = authorization
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(debit_url, headers=headers)
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Credits service unreachable: {e}")
    if resp.status_code in (401,403):
        raise HTTPException(status_code=401, detail="Unauthorized for credit debit")
    if resp.status_code != 200:
        try: data = resp.json()
        except Exception: data = {"detail": resp.text}
        raise HTTPException(status_code=402, detail=f"Credit debit failed: {data}")

# ======================
# Commit + History
# ======================
@router.post("/previews/commit")
async def commit_preview(
    payload: CommitRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    await debit_one_credit(authorization)

    base = str(request.base_url).rstrip("/")
    urls_in = payload.urls or []
    urls: List[str] = []

    if urls_in:
        urls = urls_in
    elif payload.preview_url:
        urls = [payload.preview_url]
    elif payload.preview_id:
        fs_path = os.path.join(GENERATED_DIR, f"{payload.preview_id}.png")
        if os.path.exists(fs_path):
            urls = [f"/static/generated/{payload.preview_id}.png"]
        else:
            raise HTTPException(status_code=422, detail="Preview file not found")
    else:
        raise HTTPException(status_code=422, detail="No preview reference provided")

    def to_abs(u: str) -> str:
        if u.startswith(("http://", "https://")): return u
        if u.startswith("/"): return base + u
        return urljoin(base + "/", u)

    abs_urls, seen = [], set()
    for u in urls:
        v = to_abs(str(u))
        if v not in seen:
            abs_urls.append(v); seen.add(v)

    now = datetime.utcnow()
    with engine.begin() as conn:
        res = conn.execute(
            insert(committed_posts_table).values(
                preview_id=payload.preview_id,
                urls_json=json.dumps(abs_urls),
                created_at=now,
            )
        )
        new_id = int(res.inserted_primary_key[0])

    return {"post_id": new_id, "preview_id": payload.preview_id, "urls": abs_urls, "created_at": now.isoformat() + "Z"}

@router.get("/previews/committed")
def list_committed(request: Request, limit: int = 20, offset: int = 0):
    """
    Επιστρέφει ΜΟΝΟ entries που έχουν τουλάχιστον 1 έγκυρο URL.
    Για τοπικά /static/... φιλτράρει όσα δεν υπάρχουν στον δίσκο -> έτσι ο browser δεν ζητάει ανύπαρκτα αρχεία => τέλος τα 404.
    """
    limit = max(1, min(100, int(limit))); offset = max(0, int(offset))
    base = str(request.base_url).rstrip("/")

    with engine.connect() as conn:
        rows = conn.execute(
            select(
                committed_posts_table.c.id,
                committed_posts_table.c.preview_id,
                committed_posts_table.c.urls_json,
                committed_posts_table.c.created_at,
            ).order_by(desc(committed_posts_table.c.id)).limit(limit).offset(offset)
        ).mappings().all()

    def to_abs(u: str) -> str:
        if u.startswith(("http://", "https://")): return u
        if u.startswith("/"): return base + u
        return urljoin(base + "/", u)

    out = []
    for r in rows:
        try:
            urls = json.loads(r["urls_json"] or "[]")
        except Exception:
            urls = []

        # 1) φίλτρο: κράτα μόνο όσα υπάρχουν (για τοπικά /static/…)
        valid_raw = []
        for u in urls:
            lp = _local_static_path_from_url(u)
            if lp is None:
                valid_raw.append(u)  # εξωτερικό URL: δεν το φιλτράρουμε εδώ
            else:
                if os.path.exists(lp):
                    valid_raw.append(u)
                else:
                    continue  # αγνόησέ το (αποφεύγουμε 404)

        if not valid_raw:
            # όλο το entry είναι «νεκρό» -> μην το στείλεις καθόλου
            continue

        # 2) κανονικοποίηση σε ABS
        abs_urls = [to_abs(str(u)) for u in valid_raw]

        out.append({
            "id": int(r["id"]),
            "preview_id": r["preview_id"],
            "urls": abs_urls,
            "created_at": r["created_at"].isoformat() + "Z" if r.get("created_at") else None,
        })

    return {"items": out, "limit": limit, "offset": offset, "count": len(out)}
