# production_engine/routers/ai.py
from __future__ import annotations

import re, json
from typing import List, Optional, Literal, Dict, Any
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, Field, AnyUrl

from token_module import get_current_user, create_access_token
from models import User  # type: ignore

from production_engine.services.image_check import analyze_image

router = APIRouter(prefix="/ai", tags=["ai"])

Platform = Literal["instagram", "facebook", "tiktok", "linkedin"]

class AIPlanRequest(BaseModel):
    product_url: AnyUrl
    platform: Platform = "instagram"
    ratio: Optional[Literal["1:1", "4:5", "9:16"]] = None
    extra_images: Optional[List[HttpUrl]] = None
    execute: bool = True

class ProductData(BaseModel):
    title: Optional[str] = None
    price: Optional[str] = None
    brand: Optional[str] = None
    images: List[HttpUrl] = Field(default_factory=list)

class AIPlanResult(BaseModel):
    chosen_template: str
    ratio: str
    platform: Platform
    caption: str
    render_body: Dict[str, Any]
    image_check: Dict[str, Any]

class AIPlanResponse(BaseModel):
    plan: AIPlanResult
    committed_url: Optional[str] = None
    credits_used: Optional[int] = None

OG_IMG_REGEX = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
OG_TITLE_REGEX = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.I)
PRICE_REGEX = re.compile(r'(\d+[.,]\d{2})\s?€|\€\s?(\d+[.,]\d{2})', re.I)
IMG_EXT_REGEX = re.compile(r'\.(png|jpe?g|webp|gif|bmp|svg)$', re.I)

def _app_base() -> str: return "http://127.0.0.1:8000"

def _default_ratio_for_platform(platform: Platform) -> str:
    if platform == "tiktok": return "9:16"
    if platform in ("facebook", "linkedin"): return "1:1"
    return "4:5"

def _choose_template(platform: Platform, ratio: str, has_price: bool, is_video: bool = False) -> str:
    if is_video: return f"video_basic_{ratio.replace(':', '_')}"
    if has_price: return f"img_promo_price_{ratio.replace(':', '_')}"
    return f"img_basic_promo_{ratio.replace(':', '_')}"

def _build_caption(title: Optional[str], price: Optional[str], platform: Platform) -> str:
    base = (title or "Νέο προϊόν").strip()
    price_part = f" — {price}" if price else ""
    tags = {"instagram":"#eshop #offer #new","facebook":"#eshop #offer","tiktok":"#eshop #viral","linkedin":"#eshop #business"}[platform]
    return f"{base}{price_part}\nΔες λεπτομέρειες στο link του προϊόντος.\n{tags}"

async def _fetch_product(product_url: str, timeout_sec: float = 10.0) -> ProductData:
    if IMG_EXT_REGEX.search(product_url):
        return ProductData(title="Προϊόν", price=None, images=[HttpUrl(product_url)])
    try:
        async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
            r = await client.get(product_url)
            ct = r.headers.get("content-type", "")
            if "image/" in ct:
                return ProductData(title="Προϊόν", price=None, images=[HttpUrl(product_url)])
            r.raise_for_status()
            html = r.text
    except Exception:
        demo = f"{_app_base()}/static/demo/outfit1.webp"
        return ProductData(title="Demo προϊόν", price=None, images=[HttpUrl(demo)])

    images: List[str] = []
    m = OG_IMG_REGEX.search(html)
    if m: images.append(m.group(1))
    title = None
    mt = OG_TITLE_REGEX.search(html)
    if mt: title = mt.group(1)
    price = None
    mp = PRICE_REGEX.search(html)
    if mp:
        price = mp.group(1) or mp.group(2)
        if price and not price.endswith("€"): price = f"{price}€"
    if not images:
        images = [f"{_app_base()}/static/demo/outfit1.webp"]

    out_imgs: List[HttpUrl] = []
    for u in images:
        try: out_imgs.append(HttpUrl(u))
        except Exception: pass
    if not out_imgs:
        out_imgs = [HttpUrl(f"{_app_base()}/static/demo/outfit1.webp")]

    return ProductData(title=title or "Προϊόν", price=price, images=out_imgs)

def _build_render_body(platform: Platform, ratio: str, images: List[str], caption: str,
                       overlay: Dict[str, Optional[str]], image_check: Dict[str, Any]) -> Dict[str, Any]:
    image_url = images[0] if images else f"{_app_base()}/static/demo/outfit1.webp"
    body: Dict[str, Any] = {"platform":platform,"mode":"normal","ratio":ratio,"image_url":image_url,"caption":caption}
    if any((overlay.get("title"), overlay.get("price"), overlay.get("footer"))):
        body["overlay"] = overlay
    # echo στο preview (ώστε να εμφανιστεί στο UI box)
    body["image_check"] = image_check
    return body

async def _exec_render_commit_locally(app_base: str, token: str, render_body: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=app_base, timeout=30.0, follow_redirects=True) as client:
        r1 = await client.post("/previews/render", headers=headers, content=json.dumps(render_body))
        if r1.status_code >= 400: raise HTTPException(status_code=r1.status_code, detail=f"Render failed: {r1.text}")
        data = r1.json()
        preview_url = data.get("preview_url") or data.get("url") or data.get("path")
        if not preview_url: raise HTTPException(status_code=500, detail="Render ok αλλά δεν επέστρεψε preview_url")
        r2 = await client.post("/previews/commit?wait=true&timeout=60", headers=headers, content=json.dumps({"preview_url": preview_url}))
        if r2.status_code == 402: raise HTTPException(status_code=402, detail="Insufficient credits")
        if r2.status_code >= 400: raise HTTPException(status_code=r2.status_code, detail=f"Commit failed: {r2.text}")
        return r2.json()

@router.post("/plan", response_model=AIPlanResponse)
async def ai_plan(req: AIPlanRequest, current_user: User = Depends(get_current_user)):
    pdata = await _fetch_product(str(req.product_url))
    all_images = [str(u) for u in pdata.images] + ([str(u) for u in (req.extra_images or [])])
    ratio = req.ratio or _default_ratio_for_platform(req.platform)
    chosen_template = _choose_template(req.platform, ratio, bool(pdata.price), is_video=False)
    caption = _build_caption(pdata.title, pdata.price, req.platform)

    # Image Check στο πρώτο frame
    first_img = all_images[0] if all_images else f"{_app_base()}/static/demo/outfit1.webp"
    img_check = analyze_image(first_img)

    overlay = {
        "title": pdata.title or "Προϊόν",
        "price": pdata.price or None,
        "footer": {"instagram":"#eshop #offer #new","facebook":"#eshop #offer","tiktok":"#eshop #viral","linkedin":"#eshop #business"}[req.platform]
    }

    render_body = _build_render_body(req.platform, ratio, all_images, caption, overlay, img_check)

    plan = AIPlanResult(
        chosen_template=chosen_template,
        ratio=ratio,
        platform=req.platform,
        caption=caption,
        render_body=render_body,
        image_check=img_check,
    )

    if not req.execute:
        return AIPlanResponse(plan=plan, committed_url=None)

    token = create_access_token(data={"sub": current_user.email}, expires_delta=timedelta(minutes=10))
    commit_res = await _exec_render_commit_locally(_app_base(), token, render_body)
    committed_url = commit_res.get("absolute_url") or commit_res.get("url")
    credits_used = commit_res.get("credits_used") or 1
    return AIPlanResponse(plan=plan, committed_url=committed_url, credits_used=credits_used)
