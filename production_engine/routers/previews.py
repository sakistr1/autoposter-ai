# production_engine/routers/previews.py
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import shutil
import os
import time
import mimetypes
from typing import List, Optional
from uuid import uuid4
from urllib.request import urlopen, Request as URLRequest

from database import get_db
from token_module import get_current_user
from models.user import User

router = APIRouter(tags=["previews"])

# -------------------- Utils --------------------

DEF_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

def _ensure_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _safe_ext_from_path(path: str, default: str = ".png") -> str:
    ext = (Path(path).suffix or "").lower()
    return ext if ext in DEF_EXTS else default

def _safe_ext_from_ct(content_type: Optional[str], default: str = ".png") -> str:
    if not content_type:
        return default
    guess = mimetypes.guess_extension(content_type.split(";")[0].strip()) or default
    guess = guess.lower()
    if guess == ".jpe":
        guess = ".jpg"
    return guess if guess in DEF_EXTS else default

def _is_http(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def _to_local_path_under_static(url_or_path: str) -> Path:
    p = (url_or_path or "").strip()
    if _is_http(p):
        p = urlparse(p).path
    p = p.lstrip("/")
    if not p.startswith("static/"):
        raise HTTPException(status_code=400, detail="Path must be under /static")
    return Path(p)

def _materialize_image_to_local(image_url: str) -> Path:
    """
    Επιστρέφει τοπικό Path του image_url.
    - Αν δείχνει σε /static/… (ή πλήρες URL προς /static/…), επιστρέφει Path.
    - Αν είναι ΕΞΩΤΕΡΙΚΟ http(s) URL, το κατεβάζει προσωρινά σε static/uploads/tmp/… και επιστρέφει Path.
    """
    if not image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    image_url = image_url.strip()

    # 1) /static/…
    if image_url.startswith("/static/") or (_is_http(image_url) and urlparse(image_url).path.startswith("/static/")):
        local = _to_local_path_under_static(image_url)
        if not local.exists():
            raise HTTPException(status_code=404, detail="image_url not found on server")
        return local

    # 2) Εξωτερικό URL
    if _is_http(image_url):
        tmp_dir = Path("static/uploads/tmp")
        _ensure_dir(tmp_dir)

        ext = _safe_ext_from_path(urlparse(image_url).path, default=".jpg")
        req = URLRequest(image_url, headers={"User-Agent": "autoposter-fetch/1.0"})
        try:
            with urlopen(req, timeout=10) as resp:
                ctype = resp.headers.get("Content-Type")
                if ext not in DEF_EXTS:
                    ext = _safe_ext_from_ct(ctype, default=".jpg")
                fname = f"fetch_{int(time.time()*1000)}_{uuid4().hex}{ext}"
                dest = tmp_dir / fname
                with dest.open("wb") as f:
                    shutil.copyfileobj(resp, f)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch image_url: {e}")

        return dest

    raise HTTPException(status_code=400, detail="image_url must be http(s) or /static path")

def _ext_from(src: Path, default: str = ".png") -> str:
    ext = (src.suffix or "").lower()
    return ext if ext in DEF_EXTS else default

# -------------------- Schemas --------------------

class PreviewIn(BaseModel):
    platform: str = Field(default="instagram")
    style: str = Field(default="normal")
    title: Optional[str] = None
    price: Optional[str] = None
    old_price: Optional[str] = None
    image_url: str
    brand_logo_url: Optional[str] = None
    purchase_url: Optional[str] = None
    cta_label: Optional[str] = None

class CommitIn(BaseModel):
    preview_id: str
    preview_url: str  # δέχεται /static/... ή πλήρες URL

# -------------------- Endpoints --------------------

@router.post("/previews/render")
def render_preview(body: PreviewIn,
                   request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """
    Συμβατότητα:
    - /static/ URL → χρησιμοποιείται άμεσα.
    - Εξωτερικό http(s) URL → κατεβαίνει προσωρινά σε static/uploads/tmp.
    - Κατόπιν αντιγράφουμε σε static/generated/prev_<ts>.<ext>.
    """
    src = _materialize_image_to_local(body.image_url)

    gen_dir = Path("static/generated")
    _ensure_dir(gen_dir)

    ts_ms = int(time.time() * 1000)
    ext = _ext_from(src, default=".png")
    out_name = f"prev_{ts_ms}{ext}"
    dst = gen_dir / out_name

    try:
        shutil.copy2(src, dst)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview copy failed: {e}")

    return {
        "preview_id": f"prev_{ts_ms}",
        "preview_url": "/" + str(dst).replace(os.sep, "/")
    }

@router.post("/previews/commit")
def commit_preview(body: CommitIn,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """
    In-process debit (χωρίς εσωτερικό HTTP):
    - Μειώνει credits του current_user κατά 1 (αν επαρκούν).
    - Αντιγράφει το preview σε static/generated/post_<ts>.<ext> (ρίζα, ΟΧΙ σε υποφάκελο),
      ώστε το UI που κοιτάει static/generated να το δει κατευθείαν.
    """
    # 1) Debit credits
    credits = int(getattr(current_user, "credits", 0) or 0)
    if credits < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")
    current_user.credits = credits - 1
    db.add(current_user); db.commit(); db.refresh(current_user)

    # 2) Locate preview file (δέχεται και πλήρες URL προς /static/…)
    src = _to_local_path_under_static(body.preview_url)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Preview file not found")

    # 3) Copy to static/generated/post_<ts>.<ext>
    out_dir = Path("static/generated")
    _ensure_dir(out_dir)
    ts_ms = int(time.time() * 1000)
    ext = _ext_from(src, default=src.suffix or ".png")
    out_name = f"post_{ts_ms}{ext}"
    dst = out_dir / out_name

    try:
        shutil.copy2(src, dst)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Commit copy failed: {e}")

    return {
        "ok": True,
        "preview_id": body.preview_id,
        "committed_url": "/" + str(dst).replace(os.sep, "/"),
        "remaining_credits": int(current_user.credits)
    }

@router.get("/previews/committed")
def list_committed(request: Request,
                   limit: int = Query(10, ge=1, le=100),
                   offset: int = Query(0, ge=0)):
    """
    Επιστρέφει committed previews από static/generated/.
    - Προτιμάμε post_*.* (αυτά είναι τα committed).
    - Αν ΔΕΝ υπάρχουν, κάνουμε fallback σε prev_*.* (για να μη σκάει άδειο UI).
    - Back-compat: εκτός από items=[{urls:[…], created_at}], δίνουμε
      images=[…], results=[…], committed=[{url, created_at}].
    """
    base = str(request.base_url).rstrip("/")
    gdir = Path("static/generated")
    _ensure_dir(gdir)

    post_files: List[Path] = sorted(
        [p for p in gdir.glob("post_*.*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    files = post_files
    if not files:
        # Fallback για παλιά δεδομένα: δείξε prev_* αν δεν υπάρχουν post_*
        files = sorted(
            [p for p in gdir.glob("prev_*.*") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

    total = len(files)
    slice_files = files[offset: offset + limit]

    items = []
    images = []
    committed = []

    for p in slice_files:
        url = "/" + str(p).replace(os.sep, "/")
        ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        abs_url = f"{base}{url}"
        items.append({"urls": [abs_url], "created_at": ts})
        images.append(abs_url)
        committed.append({"url": abs_url, "created_at": ts})

    return {
        "items": items,
        "images": images,       # alias (απλή λίστα URLs)
        "results": images,      # alias (πολλά frontends το περιμένουν)
        "committed": committed, # alias (λίστα αντικειμένων με url/created_at)
        "limit": limit,
        "offset": offset,
        "count": total
    }
