from __future__ import annotations

import json
import re
import time
import shutil
import sqlite3
import typing as t
from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel, ConfigDict

# σωστό auth import
from token_module import get_current_user

# ──────────────────────────────────────────────────────────────────────────────
# Imports με fallbacks
# ──────────────────────────────────────────────────────────────────────────────
try:
    from production_engine.storage import GeneratedStorage  # type: ignore
except Exception:
    class GeneratedStorage:
        def __init__(self) -> None:
            pass

_img_import_ok = False
try:
    from production_engine.utils.img_utils import (  # type: ignore
        load_image_from_url_or_path,
        save_image_rgb,
        detect_background_type,
        image_edge_density,
        image_sharpness,
    )
    _img_import_ok = True
except Exception:
    try:
        from utils.img_utils import (
            load_image_from_url_or_path,
            save_image_rgb,
            detect_background_type,
            image_edge_density,
            image_sharpness,
        )
        _img_import_ok = True
    except Exception:
        _img_import_ok = False

_vid_import_ok = False
try:
    from production_engine.utils.video_utils import (  # type: ignore
        build_video_from_images,
        build_carousel_sheet,
    )
    _vid_import_ok = True
except Exception:
    try:
        from utils.video_utils import (
            build_video_from_images,
            build_carousel_sheet,
        )
        _vid_import_ok = True
    except Exception:
        _vid_import_ok = False

_renderer_import_ok = False
try:
    from production_engine.services.pillow_renderer import pillow_render_v2  # type: ignore
    _renderer_import_ok = True
except Exception:
    try:
        from services.pillow_renderer import pillow_render_v2
        _renderer_import_ok = True
    except Exception:
        _renderer_import_ok = False

# PIL για εικόνες & QR paste
from PIL import Image, ImageDraw  # type: ignore

# Προαιρετικό: βιβλιοθήκη για QR. Αν λείπει → 422 όταν ζητάς QR.
_qr_available = True
try:
    import qrcode  # type: ignore
except Exception:
    _qr_available = False

# Fallbacks αν δεν γίνουν imports από utils.img_utils
if not _img_import_ok:
    def load_image_from_url_or_path(src: str):
        p = src.lstrip("/")
        return Image.open(p).convert("RGB")

    def save_image_rgb(im, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, "JPEG", quality=92)

    def detect_background_type(im): return "unknown"
    def image_edge_density(im): return None
    def image_sharpness(im): return None

# Fallbacks αν δεν γίνουν imports για video
if not _vid_import_ok:
    def build_video_from_images(frames, out_path: Path, fps=30, duration_sec=6):
        # fallback: αν δεν έχουμε video pipeline, σώζουμε poster jpg
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(out_path.with_suffix(".jpg"), "JPEG", quality=92)

    def build_carousel_sheet(frames):
        first = frames[0]
        sheet = frames[0]
        return first, sheet

# Fallback renderer: pass-through
if not _renderer_import_ok:
    class _RenderResult:
        def __init__(self, image):
            self.image = image
            self.flags = {}
            self.slots = {}
            self.safe_area = {"x": 0, "y": 0, "w": image.width, "h": min(image.height, image.width)}
    def pillow_render_v2(base_image, ratio, mapping):
        return _RenderResult(base_image)

# ──────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/previews", tags=["previews"])
gen = GeneratedStorage()

STATIC_ROOT = Path("static").resolve()
GENERATED = STATIC_ROOT / "generated"
GENERATED.mkdir(parents=True, exist_ok=True)

# shortlinks DB path (ίδιο με routers/shortlinks.py)
SHORTLINK_DB = Path("static/logs/database.db")

# credits DB (ΝΕΟ)
CREDITS_DB = Path("static/logs/credits.db")

IMG_EXT = ".jpg"
SHEET_EXT = ".webp"
MP4_EXT = ".mp4"

def _ts() -> int:
    return int(time.time() * 1000)

def make_id(prefix: str) -> str:
    return f"{prefix}_{_ts()}"

def gen_preview_path(prefix: str, ext: str) -> tuple[str, Path]:
    name = f"{prefix}_{_ts()}{ext}"
    rel = f"/static/generated/{name}"
    abs_p = GENERATED / name
    return rel, abs_p

def _abs_from_url(url: str) -> Path:
    p = url.lstrip("/")
    if p.startswith("static/"):
        return Path(p).resolve()
    return (STATIC_ROOT / p).resolve()

def _norm_mode(m: t.Optional[str]) -> str:
    s = (m or "").strip().lower()
    table = {
        "normal": "normal",
        "copy": "copy",
        "video": "video",
        "carousel": "carousel",
        # ελληνικά → normal
        "κανονικό": "normal", "κανονικο": "normal",
        "χιουμοριστικό": "normal", "χιουμοριστικο": "normal",
        "επαγγελματικό": "normal", "επαγγελματικο": "normal",
        # aliases
        "funny": "normal",
        "professional": "normal",
    }
    return table.get(s, "normal")

_price_num = re.compile(r"(\d+(?:[.,]\d+)?)")
def _parse_price(s: t.Optional[str]) -> t.Optional[float]:
    if not s: return None
    m = _price_num.search(s.replace(" ", ""))
    if not m: return None
    try: return float(m.group(1).replace(",", "."))
    except Exception: return None

# ──────────────────────────────────────────────────────────────────────────────
# Credits helpers (ΝΕΑ)
# ──────────────────────────────────────────────────────────────────────────────

def _credits_db():
    CREDITS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CREDITS_DB)
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        sub TEXT PRIMARY KEY,
        credits INTEGER NOT NULL
    )""")
    return con

def _get_sub(user) -> str:
    return getattr(user, "sub", None) or getattr(user, "email", None) or "demo@local"

def get_credits(user) -> int:
    sub = _get_sub(user)
    con = _credits_db()
    row = con.execute("SELECT credits FROM users WHERE sub=?", (sub,)).fetchone()
    if not row:
        con.execute("INSERT INTO users(sub, credits) VALUES (?, ?)", (sub, 200))
        con.commit()
        con.close()
        return 200
    con.close()
    return int(row[0])

def charge_credits(user, amount: int):
    if amount <= 0:
        return
    sub = _get_sub(user)
    con = _credits_db()
    row = con.execute("SELECT credits FROM users WHERE sub=?", (sub,)).fetchone()
    if not row:
        con.execute("INSERT INTO users(sub, credits) VALUES (?, ?)", (sub, max(0, 200 - amount)))
    else:
        cur = max(0, int(row[0]) - amount)
        con.execute("UPDATE users SET credits=? WHERE sub=?", (cur, sub))
    con.commit()
    con.close()

# ──────────────────────────────────────────────────────────────────────────────
# Sidecar preview metadata (ΝΕΑ)
# ──────────────────────────────────────────────────────────────────────────────

def _write_meta(preview_rel: str, meta: dict):
    """Αποθηκεύει /static/generated/<preview>.meta.json"""
    p = Path(preview_rel.lstrip("/"))
    meta_path = p.with_suffix(".meta.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))

def _read_meta(preview_rel: str) -> dict | None:
    p = Path(preview_rel.lstrip("/")).with_suffix(".meta.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None

# ──────────────────────────────────────────────────────────────────────────────
# AI background helpers (ΝΕΑ)
# ──────────────────────────────────────────────────────────────────────────────

def _apply_ai_bg_remove(im: Image.Image) -> Image.Image:
    """
    Αφαιρεί φόντο με rembg και τοποθετεί το αντικείμενο σε καθαρό λευκό background.
    Αν λείπει το rembg → 422 με οδηγία εγκατάστασης.
    """
    try:
        from rembg import remove  # type: ignore
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="ai_bg='remove' απαιτεί το πακέτο rembg. Εγκατάσταση: pip install rembg",
        )
    try:
        out = remove(im)  # μπορεί να επιστρέψει PIL Image ή bytes
        if isinstance(out, Image.Image):
            rgba = out.convert("RGBA")
        else:
            rgba = Image.open(BytesIO(out)).convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    except Exception as e:
        raise HTTPException(500, f"Background removal failed: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────

class MappingV2(BaseModel):
    title: t.Optional[str] = None
    price: t.Optional[str] = None
    old_price: t.Optional[str] = None
    cta: t.Optional[str] = None
    logo_url: t.Optional[str] = None
    discount_badge: t.Optional[bool] = None
    discount_pct: t.Optional[str] = None
    target_url: t.Optional[str] = None
    qr_enabled: t.Optional[bool] = None

class RenderRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    use_renderer: bool = True
    ratio: str = "4:5"
    mode: t.Optional[str] = "normal"

    image_url: t.Optional[str] = None
    product_image_url: t.Optional[str] = None
    brand_logo_url: t.Optional[str] = None
    logo_url: t.Optional[str] = None

    title: t.Optional[str] = None
    price: t.Optional[str] = None
    old_price: t.Optional[str] = None
    new_price: t.Optional[str] = None
    discount_pct: t.Optional[str] = None
    cta_text: t.Optional[str] = None
    target_url: t.Optional[str] = None
    qr: t.Optional[bool] = None

    # ΝΕΑ πεδία
    ai_bg: t.Optional[str] = None           # "remove" | "generate"(reserved)
    ai_bg_prompt: t.Optional[str] = None    # reserved για generate

    mapping: t.Optional[MappingV2] = None
    meta: t.Optional[t.Union[dict, str]] = None

class CommitRequest(BaseModel):
    preview_id: t.Optional[str] = None
    preview_url: t.Optional[str] = None

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_image_checks(im) -> dict:
    try: bg = detect_background_type(im)
    except Exception: bg = "unknown"
    try: ed = image_edge_density(im)
    except Exception: ed = None
    try: sh = image_sharpness(im)
    except Exception: sh = None

    suggestions = []
    if ed is not None and ed < 0.7: suggestions.append("καθάρισε φόντο")
    if sh is not None and sh < 4.0: suggestions.append("βάλε υψηλότερη ανάλυση ή πιο καθαρή φωτο")

    quality = "unknown"
    if sh is not None:
        if sh < 3.5: quality = "low"
        elif sh < 6.0: quality = "medium"
        else: quality = "high"

    return {
        "category": None,
        "background": bg or "unknown",
        "quality": quality,
        "suggestions": suggestions,
        "meta": {"edge_density": ed, "sharpness": sh},
    }

def _make_qr_pil(data: str, size_px: int) -> Image.Image:
    if not _qr_available:
        raise HTTPException(422, "QR requested but qrcode library is not installed. Run: pip install 'qrcode[pil]'")
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((size_px, size_px), Image.NEAREST)

def _paste_qr_bottom_right(base: Image.Image, qr_img: Image.Image, margin: int = 24) -> None:
    bw, bh = base.size
    q = qr_img.size[0]
    x = bw - q - margin
    y = bh - q - margin
    pad = max(6, q // 18)
    draw = ImageDraw.Draw(base)
    draw.rectangle([x - pad, y - pad, x + q + pad, y + q + pad], fill="white")
    base.paste(qr_img, (x, y))

def _shortlink_db():
    SHORTLINK_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(SHORTLINK_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS shortlinks (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, url TEXT, created_at INTEGER)"
    )
    return con

def _create_or_get_shortlink(url: str) -> str:
    """επιστρέφει absolute short URL (http://127.0.0.1:8000/go/<code>) — idempotent ανά url"""
    try:
        # Αν ήδη είναι /go/<code>, μην δημιουργείς νέο
        if re.match(r"^/go/[A-Za-z0-9]+$", url) or re.match(r"^https?://[^/]+/go/[A-Za-z0-9]+$", url):
            return url

        con = _shortlink_db()
        cur = con.cursor()
        row = cur.execute("SELECT code FROM shortlinks WHERE url=? LIMIT 1", (url,)).fetchone()
        if row:
            code = row[0]
        else:
            code = hex(int(time.time() * 1000))[2:]
            cur.execute("INSERT INTO shortlinks (code,url,created_at) VALUES (?,?,?)", (code, url, int(time.time())))
            con.commit()
        return f"http://127.0.0.1:8000/go/{code}"
    except Exception:
        # fallback: γύρνα το αρχικό url
        return url

# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/previews", tags=["previews"])

@router.post("/render")
def render_preview(
    req: RenderRequest = Body(...),
    user = Depends(get_current_user),
):
    ratio = req.ratio or "4:5"
    mode = _norm_mode(req.mode)

    # Aliases → canonical
    if not req.image_url and req.product_image_url:
        req.image_url = req.product_image_url
    if not req.logo_url and req.brand_logo_url:
        req.logo_url = req.brand_logo_url

    # Mapping
    mapping: dict = {}
    if isinstance(req.mapping, MappingV2):
        # FIX: model_dump αντί για asdict
        mapping.update(req.mapping.model_dump(exclude_none=True))
    elif isinstance(req.mapping, dict):
        mapping.update(req.mapping)

    if req.title: mapping.setdefault("title", req.title)
    if req.price: mapping.setdefault("price", req.price)
    if req.old_price: mapping.setdefault("old_price", req.old_price)
    if req.cta_text: mapping.setdefault("cta", req.cta_text)
    if req.logo_url: mapping.setdefault("logo_url", req.logo_url)
    if req.target_url: mapping.setdefault("target_url", req.target_url)
    if req.qr is not None: mapping.setdefault("qr_enabled", bool(req.qr))

    # discount_pct auto
    if not mapping.get("discount_pct"):
        old_f = _parse_price(req.old_price)
        new_f = _parse_price(req.new_price)
        if (old_f and new_f) and old_f > 0 and new_f < old_f:
            pct = int(round((1 - (new_f / old_f)) * 100))
            mapping["discount_pct"] = f"-{pct}%"
            mapping.setdefault("discount_badge", True)
    else:
        mapping.setdefault("discount_badge", True)

    # Helper για QR/shortlink από όποιο πεδίο έρθει
    def _want_qr_and_url() -> tuple[bool, str | None]:
        tgt = req.target_url or mapping.get("target_url")
        want_qr = bool(req.qr) or bool(mapping.get("qr_enabled")) or bool(tgt)
        return want_qr, tgt

    # ============= VIDEO ======================================================
    if mode == "video":
        body = json.loads(req.meta or "{}") if isinstance(req.meta, str) else (req.meta or {})
        images = body.get("images") or []
        if not images:
            try:
                body2 = json.loads(req.image_url or "{}")
                images = body2.get("images") or []
            except Exception:
                pass
        if not images:
            raise HTTPException(400, "No images for video mode")

        # PRE-FLIGHT: έλεγχος ύπαρξης όλων των paths
        missing: list[str] = []
        for it in images:
            url = it["image"] if isinstance(it, dict) else it
            try:
                if not _abs_from_url(url).exists():
                    missing.append(url)
            except Exception:
                missing.append(url)
        if missing:
            raise HTTPException(status_code=422, detail={"error": "missing_images", "missing": missing})

        frames = []
        for it in images:
            url = it["image"] if isinstance(it, dict) else it
            im = load_image_from_url_or_path(url)
            # AI background remove (αν ζητήθηκε)
            if req.ai_bg == "remove":
                im = _apply_ai_bg_remove(im)
            frames.append(im)

        # TEMPLATE OVERLAY σε κάθε frame (πριν το QR)
        try:
            rendered_frames = []
            for im0 in frames:
                try:
                    r = pillow_render_v2(base_image=im0, ratio=ratio, mapping=mapping)
                    rendered_frames.append(r.image)
                except Exception:
                    rendered_frames.append(im0)
            frames = rendered_frames
        except Exception:
            pass

        # QR/Shortlink πάνω στα frames (αν ζητήθηκε ή υπάρχει target_url)
        short_url = None
        want_qr, tgt_url = _want_qr_and_url()
        if want_qr and tgt_url:
            short_url = _create_or_get_shortlink(tgt_url)
            # μέγεθος QR 160..360 ανάλογα με το μέγεθος frame
            w0, h0 = frames[0].size
            qr_side = int(max(160, min(0.22 * min(w0, h0), 360)))
            qr_img = _make_qr_pil(short_url, qr_side)
            margin = int(0.022 * min(w0, h0))
            for i in range(len(frames)):
                _paste_qr_bottom_right(frames[i], qr_img, margin=margin)

        # paths
        mp4_rel, mp4_abs = gen_preview_path("prev", MP4_EXT)
        # build video (ή poster fallback)
        build_video_from_images(frames, mp4_abs, fps=body.get("fps", 30), duration_sec=body.get("duration_sec", 6))

        # poster (πάντα)
        poster_rel, poster_abs = gen_preview_path("prev", IMG_EXT)
        save_image_rgb(frames[0], poster_abs)

        # META: video flat cost 5
        _write_meta(poster_rel, {"type": "video", "frames": len(frames), "cost": 5})

        return {
            "status": "ok",
            "mode": "video",
            "preview_url": poster_rel,
            "absolute_url": f"http://127.0.0.1:8000{poster_rel}",
            "short_url": short_url,
            "target_url_raw": tgt_url,
            "plan": {
                "type": "video",
                "ratio": ratio,
                "video_url": mp4_rel,
                "shortlink": {"raw": tgt_url, "short": short_url},
                "image_check": {"category": "product", "quality": "ok", "background": "clean", "suggestions": [], "meta": {}},
            },
        }

    # ============= CAROUSEL ===================================================
    if mode == "carousel":
        body = json.loads(req.meta or "{}") if isinstance(req.meta, str) else (req.meta or {})
        images = body.get("images") or []
        if not images:
            try:
                body2 = json.loads(req.image_url or "{}")
                images = body2.get("images") or []
            except Exception:
                pass
        if not images:
            raise HTTPException(400, "No images for carousel mode")

        # PRE-FLIGHT: έλεγχος ύπαρξης όλων των paths
        missing: list[str] = []
        for it in images:
            url = it["image"] if isinstance(it, dict) else it
            try:
                if not _abs_from_url(url).exists():
                    missing.append(url)
            except Exception:
                missing.append(url)
        if missing:
            raise HTTPException(status_code=422, detail={"error": "missing_images", "missing": missing})

        frames = []
        for it in images:
            url = it["image"] if isinstance(it, dict) else it
            im = load_image_from_url_or_path(url)
            # AI background remove (αν ζητήθηκε)
            if req.ai_bg == "remove":
                im = _apply_ai_bg_remove(im)
            frames.append(im)

        # TEMPLATE OVERLAY σε κάθε frame (πριν το QR)
        try:
            rendered_frames = []
            for im0 in frames:
                try:
                    r = pillow_render_v2(base_image=im0, ratio=ratio, mapping=mapping)
                    rendered_frames.append(r.image)
                except Exception:
                    rendered_frames.append(im0)
            frames = rendered_frames
        except Exception:
            pass

        # QR/Shortlink πάνω σε ΚΑΘΕ frame (αν ζητήθηκε ή υπάρχει target_url)
        short_url = None
        want_qr, tgt_url = _want_qr_and_url()
        if want_qr and tgt_url:
            short_url = _create_or_get_shortlink(tgt_url)
            w0, h0 = frames[0].size
            qr_side = int(max(160, min(0.22 * min(w0, h0), 360)))
            qr_img = _make_qr_pil(short_url, qr_side)
            margin = int(0.022 * min(w0, h0))
            for i in range(len(frames)):
                _paste_qr_bottom_right(frames[i], qr_img, margin=margin)

        sheet_rel, sheet_abs = gen_preview_path("prev", SHEET_EXT)
        first_rel, first_abs = gen_preview_path("prev", SHEET_EXT)

        first_frame, sheet = build_carousel_sheet(frames)
        sheet.save(sheet_abs, "WEBP", quality=90)
        first_frame.save(first_abs, "WEBP", quality=90)

        # META: cost ανά frame
        frames_count = len(frames)
        _write_meta(sheet_rel, {"type": "carousel", "frames": frames_count, "cost": frames_count})

        return {
            "status": "ok",
            "mode": "carousel",
            "preview_url": sheet_rel,
            "absolute_url": f"http://127.0.0.1:8000{sheet_rel}",
            "sheet_url": sheet_rel,
            "first_frame_url": first_rel,
            "short_url": short_url,
            "target_url_raw": tgt_url,
            "plan": {
                "type": "carousel",
                "ratio": ratio,
                "image_check": {"category": "product", "quality": "ok", "background": "clean", "suggestions": [], "meta": {}},
            },
        }

    # ============= IMAGE (normal/copy) =======================================
    if mode in ("normal", "copy"):
        if not req.image_url:
            raise HTTPException(422, "image_url is required for normal mode")

        try:
            im = load_image_from_url_or_path(req.image_url)
        except Exception:
            rel, abs_p = gen_preview_path("prev", IMG_EXT)
            im = Image.new("RGB", (1080, 1350), (0, 0, 0))
            save_image_rgb(im, abs_p)
            # META
            _write_meta(rel, {"type": "image", "frames": 1, "cost": 1})
            return {
                "status": "ok",
                "preview_id": make_id("prev"),
                "preview_url": rel,
                "url": rel,
                "absolute_url": f"http://127.0.0.1:8000{rel}",
                "mode": mode,
                "template": None,
                "ratio": ratio,
                "overlay": None,
                "overlay_applied": False,
                "logo_applied": False,
                "discount_badge_applied": False,
                "cta_applied": False,
                "qr_applied": False,
                "slots_used": {},
                "safe_area": {"x": 0, "y": 0, "w": im.width, "h": min(im.height, im.width)},
                "image_check": {"category": None, "background": "unknown",
                                "quality": "unknown", "suggestions": [], "meta": {}},
                "meta": {"width": im.width, "height": im.height},
            }

        w, h = im.width, im.height

        # AI background remove (αν ζητήθηκε)
        if req.ai_bg == "remove":
            im = _apply_ai_bg_remove(im)

        overlay_applied = False
        logo_applied = False
        discount_applied = False
        cta_applied = False
        qr_applied = False
        slots_used: dict = {}
        safe_area = {"x": 0, "y": 0, "w": w, "h": min(h, w)}

        # Renderer overlay (αν υπάρχει)
        try:
            result = pillow_render_v2(base_image=im, ratio=ratio, mapping=mapping)
            im = result.image
            overlay_applied = True
            logo_applied = bool(getattr(result, "flags", {}).get("logo_applied"))
            discount_applied = bool(getattr(result, "flags", {}).get("discount_badge_applied"))
            cta_applied = bool(getattr(result, "flags", {}).get("cta_applied"))
            slots_used = getattr(result, "slots", {}) or {}
            safe_area = getattr(result, "safe_area", None) or safe_area
        except Exception:
            overlay_applied = False

        # ── QR + SHORTLINK integration (auto) ─────────────────────────────────
        short_url = None
        want_qr, tgt_url = _want_qr_and_url()
        if want_qr and tgt_url:
            short_url = _create_or_get_shortlink(tgt_url)
            qr_side = int(max(160, min(0.22 * min(w, h), 360)))  # 160..360px
            qr_img = _make_qr_pil(short_url, qr_side)
            _paste_qr_bottom_right(im, qr_img, margin=int(0.022 * min(w, h)))
            qr_applied = True
        # ─────────────────────────────────────────────────────────────────────

        rel, abs_p = gen_preview_path("prev", IMG_EXT)
        save_image_rgb(im, abs_p)

        # META
        _write_meta(rel, {"type": "image", "frames": 1, "cost": 1})

        checks = build_image_checks(im)
        return {
            "status": "ok",
            "preview_id": Path(rel).stem,
            "preview_url": rel,
            "url": rel,
            "absolute_url": f"http://127.0.0.1:8000{rel}",
            "mode": mode,
            "template": None,
            "ratio": ratio,
            "overlay": None,
            "overlay_applied": overlay_applied,
            "logo_applied": logo_applied,
            "discount_badge_applied": discount_applied,
            "cta_applied": cta_applied,
            "qr_applied": qr_applied,
            "short_url": short_url,
            "target_url_raw": tgt_url,
            "slots_used": slots_used,
            "safe_area": safe_area,
            "image_check": checks,
            "meta": {"width": im.width, "height": im.height},
        }

    raise HTTPException(422, f"Unsupported mode: {req.mode!s}")

# ──────────────────────────────────────────────────────────────────────────────
# Commit & Committed list
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/commit")
def commit_preview(
    req: CommitRequest = Body(...),
    user = Depends(get_current_user),
):
    if not req.preview_id and not req.preview_url:
        raise HTTPException(400, "preview_id or preview_url is required")

    src_url = None
    if req.preview_url:
        src_url = req.preview_url
    elif req.preview_id:
        candidates = [
            f"/static/generated/{req.preview_id}.jpg",
            f"/static/generated/{req.preview_id}.webp",
            f"/static/generated/{req.preview_id}.mp4",
            f"/static/generated/{req.preview_id}_sheet.webp",
        ]
        for c in candidates:
            if _abs_from_url(c).exists():
                src_url = c
                break

    if not src_url:
        raise HTTPException(404, "Preview file not found")

    # === Credits έλεγχος
    meta = _read_meta(src_url)
    cost = 1
    if meta and isinstance(meta, dict):
        try:
            cost = int(meta.get("cost", 1))
        except Exception:
            cost = 1
    current = get_credits(user)
    if current < cost:
        raise HTTPException(status_code=402, detail=f"Μη επαρκή credits: χρειάζονται {cost}, διαθέσιμα {current}")

    src_abs = _abs_from_url(src_url)
    if not src_abs.exists():
        raise HTTPException(404, "Preview file not found")

    ext = src_abs.suffix.lower()
    if ext not in (".jpg", ".webp", ".mp4"):
        ext = ".jpg"

    dst_rel, dst_abs = gen_preview_path("post", ext)
    shutil.copy2(src_abs, dst_abs)

    # Χρέωση
    charge_credits(user, cost)
    remaining = get_credits(user)

    return {
        "status": "ok",
        "ok": True,
        "preview_id": src_abs.stem,
        "committed_url": dst_rel,
        "absolute_url": f"http://127.0.0.1:8000{dst_rel}",
        "remaining_credits": remaining,
    }

@router.get("/committed")
def committed_list(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user = Depends(get_current_user),
):
    files = sorted(
        GENERATED.glob("post_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    count = len(files)
    items = []
    for p in files[offset: offset + limit]:
        rel = f"/static/generated/{p.name}"
        items.append({
            "url": rel,
            "absolute_url": f"http://127.0.0.1:8000{rel}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(p.stat().st_mtime))),
        })
    return {"ok": True, "count": count, "limit": limit, "offset": offset, "items": items}

@router.get("/health")
def health():
    return {"status": "ok", "ts": _ts()}

@router.get("/me/credits")
def me_credits(user = Depends(get_current_user)):
    return {"ok": True, "credits": get_credits(user)}
