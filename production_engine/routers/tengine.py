from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.routing import Mount
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os, re, io, time, json, base64, secrets, uuid, shutil, threading
import requests
from PIL import Image
from collections import deque

from database import get_db
from models import User, Post
from token_module import get_current_user

# Template registry
from services.template_registry import REGISTRY

# Προσπάθησε να έχεις cairosvg για PNG finals
try:
    import cairosvg  # type: ignore
    HAS_CAIROSVG = True
except Exception:
    HAS_CAIROSVG = False

router = APIRouter(prefix="/tengine", tags=["tengine"])

# ============================================================================
# Rate limit (ρυθμιζόμενο από ENV, με δυνατότητα απενεργοποίησης σε dev)
# ENV:
#   DISABLE_RATE_LIMIT=1    -> καθόλου rate limit
#   PREVIEW_RATE="600/min"  -> όριο για /preview
#   COMMIT_RATE="600/min"   -> όριο για /commit
# Δεκτές μορφές: "N/min", "N/second", "N/hour", "N", "N per min", κ.λπ.
# Στέλνουμε Retry-After σε 429.
# ============================================================================

DISABLE_RL = os.getenv("DISABLE_RATE_LIMIT", "0") == "1"

def _parse_rate(rate_str: str | None, default_n: int = 600, default_unit: str = "minute") -> tuple[int, int]:
    """Επιστρέφει (max_calls, window_seconds)."""
    if not rate_str:
        return default_n, {"second":1, "minute":60, "hour":3600}[default_unit]
    s = rate_str.strip().lower().replace("per", "/").replace(" ", "")
    try:
        n_str, unit = (s.split("/", 1) if "/" in s else (s, default_unit))
        n = int(n_str) if n_str else default_n
    except Exception:
        n, unit = default_n, default_unit
    if unit in ("s","sec","second","seconds"):
        win = 1
    elif unit in ("m","min","minute","minutes"):
        win = 60
    elif unit in ("h","hour","hours"):
        win = 3600
    else:
        win = 60
    return max(1, n), win

class _RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max = max_calls
        self.win = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> tuple[bool, int]:
        """
        True/False και πόσα δευτερόλεπτα να περιμένει ο client αν κόπηκε.
        """
        now = time.monotonic()
        with self._lock:
            dq = self._buckets.get(key)
            if dq is None:
                dq = deque()
                self._buckets[key] = dq
            cutoff = now - self.win
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) < self.max:
                dq.append(now)
                return True, 0
            # seconds μέχρι να φύγει το παλιότερο
            retry = int(self.win - (now - dq[0])) + 1
            return False, max(1, retry)

_preview_cfg = os.getenv("PREVIEW_RATE", "600/min")   # default αρκετά χαλαρό για dev
_commit_cfg  = os.getenv("COMMIT_RATE",  "600/min")

_P_MAX, _P_WIN = _parse_rate(_preview_cfg)
_C_MAX, _C_WIN = _parse_rate(_commit_cfg)

PREVIEW_LIMITER = _RateLimiter(_P_MAX, _P_WIN)
COMMIT_LIMITER  = _RateLimiter(_C_MAX, _C_WIN)

def _enforce_limit(limiter: _RateLimiter, key: str):
    if DISABLE_RL:
        return
    ok, retry = limiter.acquire(key)
    if not ok:
        # FastAPI θα στείλει το header προς τον client
        raise HTTPException(status_code=429, detail="Too Many Requests", headers={"Retry-After": str(retry)})

# ---------- Helpers ----------
def _static_dir(app) -> str:
    for r in app.routes:
        try:
            if isinstance(r, Mount) and r.path == "/static" and hasattr(r.app, "directory"):
                return os.path.abspath(r.app.directory)
        except Exception:
            continue
    raise RuntimeError("Static mount '/static' not found")

def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def _safe_text(s: str | None, maxlen=120) -> str:
    if not s: return ""
    s = re.sub(r"\s+", " ", str(s)).strip()
    s = s[:maxlen]
    return (s
            .replace("&","&amp;")
            .replace("<","&lt;")
            .replace(">","&gt;")
            .replace('"',"&quot;"))

def _safe_hex(c: str | None, default="#0fbf91") -> str:
    if not c: return default
    c = c.strip()
    if re.fullmatch(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", c):
        return c
    return default

def _safe_url(u: str | None) -> str | None:
    if not u: return None
    u = u.strip()
    if re.match(r"^https?://", u): return u
    if u.startswith("/static/"): return u
    if u.startswith("/assets/"): return u
    return None

def _ratio_to_size(ratio: str):
    if ratio == "9:16": return (1080, 1920)
    if ratio == "4:5":  return (1080, 1350)
    return (1080, 1080)  # 1:1

def _image_to_data_uri(url: str, box_w: int, box_h: int, cover=True, static_dir: str | None = None) -> str | None:
    try:
        if (url.startswith("/static/") or url.startswith("/assets/")) and static_dir:
            mount = "/static/"
            base = static_dir
            if url.startswith("/assets/"):
                base = os.path.abspath("assets")
                mount = "/assets/"
            local_path = os.path.join(base, url[len(mount):].lstrip("/"))
            with open(local_path, "rb") as fh:
                data = fh.read()
        else:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.content
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        if cover:
            rw, rh = box_w / im.width, box_h / im.height
            scale = max(rw, rh)
            nw, nh = int(im.width*scale), int(im.height*scale)
            im = im.resize((nw, nh), Image.LANCZOS)
            x = (nw - box_w)//2
            y = (nh - box_h)//2
            im = im.crop((x, y, x+box_w, y+box_h))
        else:
            rw, rh = box_w / im.width, box_h / im.height
            scale = min(rw, rh)
            nw, nh = max(1,int(im.width*scale)), max(1,int(im.height*scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            bg = Image.new("RGBA", (box_w, box_h), (0,0,0,0))
            ox = (box_w - nw)//2
            oy = (box_h - nh)//2
            bg.paste(im, (ox,oy), im)
            im = bg
        out = io.BytesIO()
        im.save(out, format="PNG")
        b64 = base64.b64encode(out.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None

def _svg_header(w:int, h:int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'

def _grad_bg(w:int, h:int, brand_color:str) -> str:
    def darken(hexcol, pct):
        hexcol = hexcol.lstrip("#")
        if len(hexcol)==3:
            hexcol = "".join([c*2 for c in hexcol])
        r = int(hexcol[0:2],16); g=int(hexcol[2:4],16); b=int(hexcol[4:6],16)
        r = max(0, min(255, int(r*(1-pct))))
        g = max(0, min(255, int(g*(1-pct))))
        b = max(0, min(255, int(b*(1-pct))))
        return f"#{r:02x}{g:02x}{b:02x}"
    c1 = brand_color
    c2 = darken(brand_color, 0.35)
    return (
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/></linearGradient></defs>'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="url(#bg)"/>'
    )

def _write_svg(meta: dict, out_path: str, is_preview: bool, static_dir: str):
    ratio = meta.get("ratio") or "1:1"
    W, H = _ratio_to_size(ratio)
    title = _safe_text(meta.get("title"), 120)
    price = _safe_text(meta.get("price"), 60)
    image_url = meta.get("image_url") or ""
    brand_color = _safe_hex(meta.get("brand_color") or "#0fbf91")
    logo_url = _safe_url(meta.get("logo_url") or "") or ""
    cta_text = _safe_text(meta.get("cta_text"), 40)
    badge_text = _safe_text(meta.get("badge_text"), 20)

    product_img = _image_to_data_uri(image_url, int(W*0.9), int(H*0.55), cover=True, static_dir=static_dir) if image_url else None
    logo_img    = _image_to_data_uri(logo_url, 200, 80, cover=False, static_dir=static_dir) if logo_url else None

    parts = [ _svg_header(W,H), _grad_bg(W,H, brand_color) ]

    if product_img:
        parts.append(f'<image href="{product_img}" x="{int(W*0.05)}" y="{int(H*0.12)}" width="{int(W*0.9)}" height="{int(H*0.55)}" />')
    if title:
        parts.append(f'<text x="{W//2}" y="{int(H*0.76)}" text-anchor="middle" font-family="system-ui,Segoe UI,Roboto" font-size="{int(H*0.06)}" fill="#ffffff" font-weight="700">{title}</text>')
    if price:
        parts.append(f'<text x="{W//2}" y="{int(H*0.86)}" text-anchor="middle" font-family="system-ui,Segoe UI,Roboto" font-size="{int(H*0.05)}" fill="#ffffff" font-weight="600">{price}</text>')
    if badge_text:
        parts.append(f'<rect x="{int(W*0.05)}" y="{int(H*0.05)}" rx="14" ry="14" width="220" height="44" fill="#ffffffaa"/><text x="{int(W*0.05)+110}" y="{int(H*0.05)+30}" text-anchor="middle" font-family="system-ui" font-size="20" fill="#111">{badge_text}</text>')
    if cta_text:
        parts.append(f'<rect x="{int(W*0.65)}" y="{int(H*0.89)}" rx="12" ry="12" width="{int(W*0.28)}" height="42" fill="#ffffff"/>'
                     f'<text x="{int(W*0.65)+int(W*0.14)}" y="{int(H*0.89)+28}" text-anchor="middle" font-family="system-ui" font-size="20" fill="#111">{cta_text}</text>')
    if logo_img:
        parts.append(f'<image href="{logo_img}" x="{int(W*0.05)}" y="{int(H*0.88)}" width="200" height="80" />')

    if is_preview:
        parts.append(f'<text x="{W-8}" y="{H-8}" text-anchor="end" font-family="system-ui" font-size="12" fill="#ffffffaa">Preview</text>')

    parts.append('</svg>')
    svg = "".join(parts)
    _ensure_dir(os.path.dirname(out_path))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

def _normalize_preview_url_to_static_path(preview_url: str) -> str:
    if not preview_url:
        raise HTTPException(status_code=400, detail="preview_url is required")
    from urllib.parse import urlparse
    parsed = urlparse(preview_url)
    path = parsed.path if parsed.scheme else preview_url
    if not path.startswith("/"):
        path = "/" + path
    return path

# --- Render finals (PNG αν υπάρχει cairosvg, αλλιώς SVG copy) ---
def _final_from_preview(preview_static_path: str, static_dir: str) -> str:
    if not preview_static_path.startswith("/static/generated/previews/"):
        raise HTTPException(status_code=400, detail="Invalid preview_url")

    src = os.path.join(static_dir, preview_static_path.replace("/static/", "").lstrip("/").replace("/", os.sep))
    if not os.path.isfile(src):
        raise HTTPException(status_code=404, detail="Preview file not found")

    finals_dir = os.path.join(static_dir, "generated", "finals")
    _ensure_dir(finals_dir)

    uid = uuid.uuid4().hex
    if HAS_CAIROSVG:
        # PNG render
        final_name = f"final_{uid}.png"
        dst = os.path.join(finals_dir, final_name)
        try:
            svg_text = open(src, "r", encoding="utf-8").read()
        except UnicodeDecodeError:
            svg_text = open(src, "r", encoding="latin-1", errors="ignore").read()
        cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), write_to=dst)
        rel = os.path.relpath(dst, static_dir).replace(os.sep, "/")
        return f"/static/{rel}"
    else:
        # Fallback: SVG copy
        final_name = f"final_{uid}.svg"
        dst = os.path.join(finals_dir, final_name)
        shutil.copyfile(src, dst)
        rel = os.path.relpath(dst, static_dir).replace(os.sep, "/")
        return f"/static/{rel}"

# ---------- Schemas ----------
class PreviewIn(BaseModel):
    post_type: str = "image"
    mode: str | None = None
    ratio: str = "1:1"
    title: str | None = None
    price: str | None = None
    image_url: str | None = None
    brand_color: str | None = None
    logo_url: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    badge_text: str | None = None
    template_id: str | None = None  # render μέσω registry αν δοθεί

class CommitIn(BaseModel):
    preview_url: str
    post_type: str = "image"
    product_id: int | None = None
    caption: str | None = None

# ---------- Endpoints ----------
@router.post("/preview")
def preview(req: Request, payload: PreviewIn, current_user: User = Depends(get_current_user)):
    # Rate limit ανά χρήστη
    _enforce_limit(PREVIEW_LIMITER, f"user:{current_user.id}:preview")

    static_dir = _static_dir(req.app)
    prev_dir = os.path.join(static_dir, "generated", "previews")
    _ensure_dir(prev_dir)

    pid = secrets.token_hex(16)
    svg_name = f"preview_{pid}.svg"
    svg_path = os.path.join(prev_dir, svg_name)

    # render μέσω registry όταν έχει template_id
    if payload.template_id:
        try:
            rec = REGISTRY.get(payload.template_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown template_id")

        ratio = payload.ratio or None
        incoming = {
            "title": payload.title,
            "price": payload.price,
            "image_url": payload.image_url,
            "brand_color": payload.brand_color,
            "badge_text": payload.badge_text,
            "cta_text": payload.cta_text,
            "cta_url": payload.cta_url,
            "logo": payload.logo_url,  # map
        }
        incoming = {k: v for k, v in incoming.items() if v not in (None, "")}

        try:
            context, warnings = REGISTRY.validate_and_merge(rec, incoming, ratio)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        svg = REGISTRY.render_svg(rec, context)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg)

        # meta για debug
        meta = {
            "template_id": payload.template_id,
            "ratio": context.get("ratio"),
            "payload": incoming,
            "_meta": {"version": "v3", "created_ts": time.time(), "user_id": current_user.id}
        }
        with open(os.path.join(prev_dir, f"meta_{pid}.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

        return {
            "preview_url": f"/static/generated/previews/{svg_name}",
            "warnings": warnings,
            "template_id": payload.template_id,
            "ratio": context.get("ratio")
        }

    # ------ Fallback: απλός renderer χωρίς template_id ------
    meta = payload.dict()
    meta["ratio"] = (meta.get("ratio") or "1:1")
    meta["brand_color"] = _safe_hex(meta.get("brand_color"))
    meta["title"] = _safe_text(meta.get("title") or "Autoposter", 120)
    meta["price"] = _safe_text(meta.get("price") or "", 60)
    meta["image_url"] = meta.get("image_url") or ""
    meta["logo_url"] = meta.get("logo_url") or ""
    meta["cta_text"] = _safe_text(meta.get("cta_text") or "", 40)
    meta["cta_url"] = meta.get("cta_url") or ""
    meta["badge_text"] = _safe_text(meta.get("badge_text") or "", 20)
    meta["_meta"] = {"version": "v3", "created_ts": time.time(), "user_id": current_user.id}

    with open(os.path.join(prev_dir, f"meta_{pid}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    _write_svg(meta, svg_path, is_preview=True, static_dir=static_dir)
    return {"preview_url": f"/static/generated/previews/{svg_name}"}

@router.post("/commit")
def commit(req: Request, body: CommitIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Rate limit ανά χρήστη
    _enforce_limit(COMMIT_LIMITER, f"user:{current_user.id}:commit")

    if current_user.credits is None or current_user.credits < 1:
        raise HTTPException(status_code=402, detail="Not enough credits")
    # χρέωση πρώτα (debounce spam)
    current_user.credits -= 1
    db.add(current_user); db.commit(); db.refresh(current_user)

    static_dir = _static_dir(req.app)
    normalized_path = _normalize_preview_url_to_static_path(body.preview_url)
    final_url = _final_from_preview(normalized_path, static_dir)  # PNG by default

    media_urls = [final_url]
    post = Post(
        product_id=body.product_id,
        type=body.post_type,
        media_urls=json.dumps(media_urls),
        owner_id=current_user.id,
    )
    if hasattr(Post, "caption") and body.caption is not None:
        try: setattr(post, "caption", body.caption)
        except Exception: pass
    if hasattr(Post, "content"):
        try: setattr(post, "content", body.caption or "")
        except Exception: pass
    if hasattr(Post, "title") and getattr(post, "title", None) is None:
        try: setattr(post, "title", "Autoposter Image")
        except Exception: pass

    db.add(post); db.commit(); db.refresh(post)
    return {"post_id": post.id, "media_urls": media_urls, "credits_left": current_user.credits}
