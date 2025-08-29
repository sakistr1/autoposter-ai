# production_engine/services/image_check.py
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request as URLRequest
from typing import Dict, Optional
import time, shutil, os

try:
    from PIL import Image, ImageFilter, ImageStat
except Exception:  # pragma: no cover
    Image = None
    ImageFilter = None
    ImageStat = None

STATIC_DIR = Path("static")
TMP_DIR = STATIC_DIR / "uploads" / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

SAFE_MIN_DIM = 600  # ελάχιστη διάσταση για "ok" ποιότητα

def _is_http(u: str) -> bool:
    return u.startswith("http://") or u.startswith("https://")

def _to_static_path(u: str) -> Optional[Path]:
    p = (u or "").strip()
    if not p:
        return None
    if _is_http(p):
        p = urlparse(u).path
    p = p.lstrip("/")
    if p.startswith("static/"):
        return Path(p)
    return None

def _download_temp(u: str) -> Path:
    ext = Path(urlparse(u).path).suffix or ".jpg"
    name = f"imgchk_{int(time.time()*1000)}{ext}"
    dest = TMP_DIR / name
    req = URLRequest(u, headers={"User-Agent": "autoposter-imagecheck/1.0"})
    with urlopen(req, timeout=10) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest

def _open_image(local: Path):
    if Image is None:
        return None
    try:
        im = Image.open(local)
        im.load()
        return im
    except Exception:
        return None

def _edge_density(gray_im) -> float:
    # proxy μέτρηση "μπερδεμένου" background
    try:
        edges = gray_im.filter(ImageFilter.FIND_EDGES)
        # μείωσε μέγεθος για ταχύτητα
        small = edges.resize((256, max(1, int(256 * gray_im.height / max(1, gray_im.width)))), Image.BILINEAR)
        # υπολόγισε πόσα pixels είναι "μη μηδενικά"
        hist = small.histogram()
        total = small.size[0] * small.size[1]
        # προσεγγιστικά: αν το grayscale > 10 θεωρείται edge
        non_zero = total - hist[0] if len(hist) > 0 else 0
        return float(non_zero) / float(total or 1)
    except Exception:
        return 0.0

def _sharpness(gray_im) -> float:
    # proxy sharpness: μέση τιμή edges
    try:
        edges = gray_im.filter(ImageFilter.FIND_EDGES)
        st = ImageStat.Stat(edges)
        mean = sum(st.mean) / len(st.mean) if isinstance(st.mean, (list, tuple)) else float(st.mean)
        return float(mean)
    except Exception:
        return 0.0

def _guess_category_from_name(path_or_url: str) -> Optional[str]:
    name = Path(urlparse(path_or_url).path).stem.lower()
    for key, cat in [
        ("shoe", "shoes"), ("sneaker", "shoes"), ("boot", "shoes"),
        ("dress", "dress"), ("skirt", "skirt"),
        ("shirt", "tshirt"), ("tshirt", "tshirt"), ("tee", "tshirt"),
        ("bag", "bag"), ("watch", "watch"),
        ("skin", "skincare"), ("cream", "skincare"), ("serum", "skincare"),
        ("jean", "jeans"), ("pants", "pants")
    ]:
        if key in name:
            return cat
    return None

def analyze_image(url_or_path: str) -> Dict:
    """
    Επιστρέφει:
      {
        "category": "...",
        "background": "clean" | "busy",
        "quality": "ok" | "low",
        "suggestions": [ ... ],
        "meta": { "width":..., "height":..., "edge_density":..., "sharpness":... }
      }
    """
    # 1) εντόπισε/κατέβασε
    local: Optional[Path] = _to_static_path(url_or_path)
    tmp_downloaded = False
    if local is None:
        if _is_http(url_or_path):
            try:
                local = _download_temp(url_or_path)
                tmp_downloaded = True
            except Exception:
                return {
                    "category": None,
                    "background": "unknown",
                    "quality": "unknown",
                    "suggestions": ["δεν ήταν δυνατή η ανάγνωση εικόνας"],
                    "meta": {}
                }
        else:
            return {
                "category": None,
                "background": "unknown",
                "quality": "unknown",
                "suggestions": ["μη έγκυρο path εικόνας"],
                "meta": {}
            }

    im = _open_image(local)
    if im is None:
        if tmp_downloaded:
            try: os.remove(local)  # noqa
            except Exception: pass
        return {
            "category": None,
            "background": "unknown",
            "quality": "unknown",
            "suggestions": ["δεν ήταν δυνατή η φόρτωση εικόνας"],
            "meta": {}
        }

    try:
        # 2) μετρήσεις
        w, h = im.size
        gray = im.convert("L")
        ed = _edge_density(gray)           # 0..1
        sharp = _sharpness(gray)           # τυπικά 0..~40+ ανάλογα με την εικόνα

        # thresholds (πρακτικά)
        background = "busy" if ed > 0.22 else "clean"
        quality = "ok" if (min(w, h) >= SAFE_MIN_DIM and sharp >= 4.0) else "low"

        cat = _guess_category_from_name(str(local))

        suggestions = []
        if background == "busy":
            suggestions.append("καθάρισε φόντο")
        if quality == "low":
            suggestions.append("βάλε υψηλότερη ανάλυση ή πιο καθαρή φωτο")
        if cat in {"tshirt", "dress", "shoes"} and h < w:
            # για fashion θέλουμε portrait για IG 4:5
            suggestions.append("προτίμησε κάθετη λήψη (4:5)")

        return {
            "category": cat,
            "background": background,
            "quality": quality,
            "suggestions": suggestions,
            "meta": {
                "width": w, "height": h,
                "edge_density": round(ed, 3),
                "sharpness": round(sharp, 3)
            }
        }
    finally:
        if tmp_downloaded:
            try: os.remove(local)  # noqa
            except Exception: 
                pass
