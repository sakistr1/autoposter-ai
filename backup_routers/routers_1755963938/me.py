# routers/me.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os, json, time
from pathlib import Path

from database import get_db
from models import User, Post
from token_module import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


# ---------- Helpers ----------
def _get_static_dir() -> str:
    """Εντοπίζει το directory του /static mount στο main app."""
    try:
        from main import app as main_app  # late import για να μην έχουμε κυκλικό
    except Exception:
        raise HTTPException(status_code=500, detail="main app not available")

    for r in getattr(main_app, "routes", []):
        try:
            if getattr(r, "path", None) == "/static" and hasattr(r.app, "directory"):
                return r.app.directory
        except Exception:
            continue
    raise HTTPException(status_code=500, detail="static mount not found")


def _safe_fs_path_under(base_dir: str, url_path: str) -> Path:
    """
    Μετατρέπει /static/... URL σε ασφαλές filesystem path κάτω από το base_dir.
    """
    if not url_path.startswith("/static/"):
        raise HTTPException(status_code=400, detail="invalid media url")

    rel = url_path[len("/static/"):].lstrip("/")
    base = Path(base_dir).resolve()
    fs_path = (base / rel).resolve()
    try:
        fs_path.relative_to(base)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid path traversal")
    return fs_path


# ---------- Schemas ----------
class WooCreds(BaseModel):
    # ΝΕΑ ονόματα (προτιμώμενα)
    woocommerce_url: str | None = None
    consumer_key: str | None = None
    consumer_secret: str | None = None
    sync_url: str | None = None
    # ΠΑΛΙΑ aliases (υποστήριξη συμβατότητας)
    url: str | None = None
    ck: str | None = None
    cs: str | None = None


# ---------- Credits ----------
@router.get("/credits")
def credits(current_user: User = Depends(get_current_user)):
    return {"credits": int(current_user.credits or 0)}


# ---------- Woo credentials ----------
@router.get("/woocommerce-credentials")
def get_wc(current_user: User = Depends(get_current_user)):
    """
    Επιστρέφει τόσο τα νέα όσο και τα παλιά κλειδιά, για να μην σπάει κανένα frontend.
    """
    has = bool(
        current_user.woocommerce_url and current_user.consumer_key and current_user.consumer_secret
    )
    return {
        # νέα
        "woocommerce_url": current_user.woocommerce_url,
        "consumer_key": current_user.consumer_key,
        "consumer_secret": current_user.consumer_secret,
        "sync_url": current_user.sync_url,
        "has_credentials": has,
        # παλιά (back-compat)
        "url": current_user.woocommerce_url,
        "ck": current_user.consumer_key,
        "cs": current_user.consumer_secret,
    }


@router.post("/woocommerce-credentials")
def set_wc(
    body: WooCreds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Δέχεται και τα δύο σχήματα πεδίων (νέο/παλιό). Προτεραιότητα στα νέα.
    """
    current_user.woocommerce_url = body.woocommerce_url or body.url
    current_user.consumer_key = body.consumer_key or body.ck
    current_user.consumer_secret = body.consumer_secret or body.cs
    current_user.sync_url = body.sync_url

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"ok": True}


# ---------- Posts list ----------
@router.get("/posts")
def my_posts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(Post)
        .filter(Post.owner_id == current_user.id)
        .order_by(Post.id.desc())
        .limit(50)
        .all()
    )
    out = []
    for p in rows:
        try:
            media = json.loads(p.media_urls) if isinstance(p.media_urls, str) else (p.media_urls or [])
        except Exception:
            media = []
        out.append({
            "id": p.id,
            "title": getattr(p, "title", "") or "Autoposter Post",
            "caption": getattr(p, "caption", "") or "",
            "post_type": getattr(p, "post_type", "image"),
            "status": getattr(p, "status", "pending"),
            "created_at": getattr(p, "created_at", None),
            "media_urls": media,
        })
    return out


# ---------- Επιστροφή PNG αρχείου για post ----------
@router.get("/posts/{post_id}/png")
def post_png(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Παίρνει το πρώτο media URL του post:
    - Αν είναι PNG/JPG/WEBP κάτω από /static → επιστρέφει το ίδιο αρχείο.
    - Αν (legacy) είναι SVG → το μετατρέπει σε PNG με cairosvg και επιστρέφει το PNG.
    """
    p = db.query(Post).filter(Post.id == post_id, Post.owner_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="post not found")

    try:
        media = json.loads(p.media_urls) if isinstance(p.media_urls, str) else (p.media_urls or [])
    except Exception:
        media = []
    if not media:
        raise HTTPException(status_code=404, detail="no media")

    url0 = str(media[0])
    static_dir = _get_static_dir()
    fs_path = _safe_fs_path_under(static_dir, url0)

    if not fs_path.exists():
        raise HTTPException(status_code=404, detail="file not found on disk")

    ext = fs_path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        # Επιστροφή του υπάρχοντος αρχείου
        mt = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(ext, "application/octet-stream")
        return FileResponse(str(fs_path), media_type=mt, filename=fs_path.name)

    if ext == ".svg":
        # Legacy preview-only media: μετατροπή σε PNG on-the-fly
        try:
            from cairosvg import svg2png  # local import για να μην είναι hard dep όταν δεν χρειάζεται
        except Exception:
            raise HTTPException(status_code=500, detail="cairosvg is required to convert SVG to PNG")

        out_dir = Path(static_dir) / "generated" / "png"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"post_{post_id}.png"
        svg2png(url=str(fs_path), write_to=str(out_path))
        return FileResponse(str(out_path), media_type="image/png", filename=out_path.name)

    # Μη αναγνωρίσιμη μορφή
    raise HTTPException(status_code=415, detail=f"unsupported media type: {ext}")


# ---------- Upload logo (με ελέγχους) ----------
@router.post("/upload-logo")
def upload_logo(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # MIME & μέγεθος
    allowed = {"image/png", "image/jpeg", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail="Unsupported file type")
    contents = file.file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 2MB)")

    # Verify με Pillow
    from PIL import Image
    import io
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image")

    static_dir = _get_static_dir()

    # Save ως PNG
    uploads = Path(static_dir) / "uploads" / "logos"
    uploads.mkdir(parents=True, exist_ok=True)
    fname = f"logo_{current_user.id}_{int(time.time())}.png"
    fpath = uploads / fname

    img = Image.open(io.BytesIO(contents)).convert("RGBA")
    img.save(str(fpath), format="PNG")

    rel = fpath.relative_to(Path(static_dir)).as_posix()
    url = f"/static/{rel}"
    return {"url": url, "logo_url": url}
