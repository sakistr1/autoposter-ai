# production_engine/routers/manual.py
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from token_module import get_current_user, create_access_token
from models import User  # type: ignore

from production_engine.services.image_check import analyze_image

router = APIRouter(prefix="/manual", tags=["manual"])

Platform = Literal["instagram", "facebook", "tiktok", "linkedin"]

class ManualPlanIn(BaseModel):
    platform: Platform = "instagram"
    ratio: Optional[Literal["1:1", "4:5", "9:16"]] = None
    execute: bool = True
    title: str
    price: Optional[str] = None
    old_price: Optional[str] = None
    caption: Optional[str] = None
    footer: Optional[str] = None
    images: List[HttpUrl] = Field(default_factory=list)

class PlanResult(BaseModel):
    ratio: str
    platform: Platform
    caption: str
    render_body: Dict[str, Any]
    image_check: Dict[str, Any]

class ManualPlanOut(BaseModel):
    plan: PlanResult
    committed_url: Optional[str] = None
    credits_used: Optional[int] = None

def _app_base() -> str: return "http://127.0.0.1:8000"

def _default_ratio(platform: Platform) -> str:
    if platform == "tiktok": return "9:16"
    if platform in ("facebook", "linkedin"): return "1:1"
    return "4:5"

def _default_footer(platform: Platform) -> str:
    return {"instagram":"#eshop #offer #new","facebook":"#eshop #offer","tiktok":"#eshop #viral","linkedin":"#eshop #business"}[platform]

def _build_caption(title: str, price: Optional[str], platform: Platform, custom: Optional[str]) -> str:
    if custom and custom.strip(): return custom.strip()
    base = title.strip() or "Νέο προϊόν"
    price_part = f" — {price}" if price else ""
    return f"{base}{price_part}\nΔες λεπτομέρειες στο link του προϊόντος.\n{_default_footer(platform)}"

def _build_render_body(platform: Platform, ratio: str, images: List[str], caption: str,
                       overlay: Dict[str, Optional[str]], image_check: Dict[str, Any]) -> Dict[str, Any]:
    if not images: raise HTTPException(status_code=422, detail="images[] απαιτεί τουλάχιστον 1 URL")
    image_url = images[0]
    body: Dict[str, Any] = {"platform":platform,"mode":"normal","ratio":ratio,"image_url":image_url,"caption":caption}
    if any((overlay.get("title"), overlay.get("price"), overlay.get("footer"))):
        body["overlay"] = overlay
    body["image_check"] = image_check
    return body

async def _exec_render_commit(app_base: str, token: str, render_body: Dict[str, Any]) -> Dict[str, Any]:
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

@router.post("/plan", response_model=ManualPlanOut)
async def manual_plan(body: ManualPlanIn, current_user: User = Depends(get_current_user)):
    if not body.images:
        raise HTTPException(status_code=422, detail="images[] είναι υποχρεωτικό")

    ratio = body.ratio or _default_ratio(body.platform)
    caption = _build_caption(body.title, body.price, body.platform, body.caption)

    first_img = str(body.images[0])
    img_check = analyze_image(first_img)

    overlay = {"title": body.title, "price": body.price, "footer": body.footer or _default_footer(body.platform)}

    render_body = _build_render_body(
        platform=body.platform,
        ratio=ratio,
        images=[str(u) for u in body.images],
        caption=caption,
        overlay=overlay,
        image_check=img_check,
    )

    plan = PlanResult(ratio=ratio, platform=body.platform, caption=caption, render_body=render_body, image_check=img_check)

    if not body.execute:
        return ManualPlanOut(plan=plan, committed_url=None)

    token = create_access_token(data={"sub": current_user.email}, expires_delta=timedelta(minutes=10))
    commit_res = await _exec_render_commit(_app_base(), token, render_body)
    committed_url = commit_res.get("absolute_url") or commit_res.get("url")
    credits_used = commit_res.get("credits_used") or 1
    return ManualPlanOut(plan=plan, committed_url=committed_url, credits_used=credits_used)
