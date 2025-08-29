from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
import re
import httpx
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from database import get_db
from token_module import get_current_user
from models.user import User

# θα καλέσουμε απευθείας τα helpers του previews router
from production_engine.routers import previews as previews_router
from production_engine.routers.previews import PreviewIn, CommitIn

router = APIRouter(prefix="/ai", tags=["ai"])

# --------- Schemas ---------

class AIPlanIn(BaseModel):
    product_url: str
    platform: str = Field(default="instagram")
    ratio: Optional[str] = None
    extra_images: Optional[List[str]] = None


class AIPlanOut(BaseModel):
    ok: bool = True
    plan: Dict[str, Any]
    committed_url: Optional[str] = None
    absolute_url: Optional[str] = None
    credits_used: int = 0


# --------- Simple product fetchers (MVP) ---------

async def _fetch_product_data(product_url: str) -> Dict[str, Any]:
    """
    MVP:
    - Αν είναι demo/local, επιστρέφουμε έτοιμα.
    - Αν είναι http(s), προσπαθούμε να διαβάσουμε <title> και πιθανή τιμή με regex.
    """
    u = product_url.strip()

    # Demo shortcuts (στατικά αρχεία που ήδη έχεις)
    demo_map = {
        "outfit1":  {"images": ["/static/demo/outfit1.webp"], "title": "Outfit #1", "price": "€49.90", "brand": "DemoBrand"},
        "shoes1":   {"images": ["/static/demo/shoes1.webp"],  "title": "Shoes #1",  "price": "€59.00", "brand": "DemoBrand"},
        "outfit2":  {"images": ["/static/demo/outfit2.webp"], "title": "Outfit #2", "price": "€59.90", "brand": "DemoBrand"},
    }
    for key, val in demo_map.items():
        if key in u:
            return {**val, "source": "demo", "product_url": u}

    # Επιτρέπουμε και /static/... κατευθείαν
    if u.startswith("/static/"):
        return {
            "images": [u],
            "title": "Product",
            "price": "€00.00",
            "brand": "Local",
            "source": "static",
            "product_url": u,
        }

    # Αν είναι έγκυρο http(s), δοκιμάζουμε να διαβάσουμε λίγο HTML για τίτλο/τιμή
    parsed = urlparse(u)
    if parsed.scheme in ("http", "https"):
        try:
            # Timeout μικρό για να μην κρεμάει
            async with httpx.AsyncClient(timeout=6.0, headers={"User-Agent": "autoposter-ai/1.0"}) as cli:
                resp = await cli.get(u)
                html = resp.text or ""
            title = _extract_title(html) or "Product"
            price = _extract_price(html) or "€00.00"
            # Προσπαθούμε να βρούμε εικόνες (MVP πολύ light)
            imgs = _extract_images(html) or []
            # Κόβουμε τις πάρα πολλές
            if len(imgs) > 4:
                imgs = imgs[:4]
            return {
                "images": imgs,
                "title": title,
                "price": price,
                "brand": urlparse(u).hostname or "Brand",
                "source": "fetch",
                "product_url": u,
            }
        except Exception:
            # Δεν θέλω να ρίχνω 500—επιστρέφω έντιμα ότι δεν ξέρουμε
            raise HTTPException(status_code=422, detail="Could not fetch product data from URL")
    # Οτιδήποτε άλλο το κόβουμε
    raise HTTPException(status_code=422, detail="Unknown product_url (χρησιμοποίησε demo: outfit1/shoes1/outfit2 ή /static/...)")

def _extract_title(html: str) -> Optional[str]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I|re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return None

def _extract_price(html: str) -> Optional[str]:
    m = re.search(r"(\€\s?\d+[.,]?\d{0,2}|\d+[.,]\d{2}\s?€)", html)
    return m.group(1).strip() if m else None

def _extract_images(html: str) -> List[str]:
    urls: List[str] = []
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, flags=re.I):
        src = m.group(1).strip()
        if src.startswith("http://") or src.startswith("https://") or src.startswith("/static/"):
            urls.append(src)
    # μικρό φιλτράρισμα
    urls = [u for u in urls if not any(ext in u.lower() for ext in (".svg", ".gif"))]
    return urls


# --------- Caption / Template selection (MVP) ---------

def _pick_template(platform: str, ratio: Optional[str]) -> Dict[str, Any]:
    plat = (platform or "instagram").lower()
    r = (ratio or "4:5").strip()
    if plat == "instagram":
        if r in ("4:5", "4/5", "0.8"):
            return {"template": "img_basic_promo_4_5", "ratio": "4:5"}
        if r in ("1:1", "1/1", "1"):
            return {"template": "img_basic_square", "ratio": "1:1"}
        # default
        return {"template": "img_basic_promo_4_5", "ratio": "4:5"}
    # άλλα platforms ίσως αργότερα
    return {"template": "img_basic_promo_4_5", "ratio": "4:5"}

def _build_caption(title: str, price: Optional[str], product_url: str) -> str:
    t = (title or "Product").strip()
    p = (price or "").strip()
    parts = [t]
    if p:
        parts.append(f"— {p}")
    parts.append(f"Προϊόν\nΔες λεπτομέρειες στο link του προϊόντος.\n#eshop #offer #new")
    caption = " ".join(parts)
    # απλό CTA κάτω-κάτω
    caption += f"\n{product_url}"
    return caption


# --------- Endpoint ---------

@router.post("/plan", response_model=AIPlanOut)
async def ai_plan(
    body: AIPlanIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    1) Fetch (ή demo) product data: images, title, price, brand
    2) Επιλογή template/ratio
    3) Caption
    4) Render (image ή video: εδώ κρατάμε image για MVP)
    5) Commit (wait) και επιστροφή absolute_url
    """
    # 1) fetch product
    pdata = await _fetch_product_data(body.product_url)
    images = list(pdata.get("images") or [])
    if body.extra_images:
        images.extend([u for u in body.extra_images if u and u not in images])

    if not images:
        raise HTTPException(status_code=422, detail="No images found for product")

    # 2) template
    tsel = _pick_template(body.platform, body.ratio)
    ratio = tsel["ratio"]
    template = tsel["template"]

    # 3) caption
    caption = _build_caption(pdata.get("title") or "Product", pdata.get("price"), pdata.get("product_url") or body.product_url)

    # 4) Render (image mode για MVP: παίρνουμε το πρώτο)
    render_in = PreviewIn(
        platform=body.platform or "instagram",
        mode="normal",
        ratio=ratio,
        image_url=images[0],
        overlay=None,  # overlay θα μπει σε επόμενο γύρο όταν φτιάξουμε engine
        template=template,
        title=pdata.get("title"),
    )
    # Χρησιμοποιούμε απευθείας το handler του previews (όχι HTTP)
    r = previews_router.render_preview(render_in, request, db=db, user=user)

    # 5) Commit (wait=true, timeout=60)
    c = previews_router.commit_preview(
        CommitIn(preview_url=r.get("preview_url")),
        request,
        db=db,
        current_user=user,
        wait=True,
        timeout=60,
    )

    # Response
    plan_out: Dict[str, Any] = {
        "chosen_template": template,
        "ratio": ratio,
        "platform": body.platform,
        "caption": caption,
        "render_body": {
            "platform": body.platform,
            "mode": "normal",
            "ratio": ratio,
            "image_url": images[0],
            "caption": caption,
        },
    }
    return AIPlanOut(
        ok=True,
        plan=plan_out,
        committed_url=c.get("committed_url"),
        absolute_url=c.get("absolute_url"),
        credits_used=1,
    )
