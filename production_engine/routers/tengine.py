# tengine.py
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
import httpx

# import ai_plan service
from production_engine.routers.ai_plan import ai_plan
router = APIRouter(prefix="/tengine", tags=["tengine"])


class TenPreviewIn(BaseModel):
    platform: Optional[str] = None
    ratio: Optional[str] = None
    mode: Optional[str] = Field(default="normal")
    image_url: Optional[str] = None
    mapping: Optional[Dict[str, Any]] = None
    watermark: Optional[bool] = None
    return_absolute_url: Optional[bool] = True
    use_renderer: bool = False
    # ΝΕΟ: flag για ai_plan
    use_ai_plan: bool = False
    product_url: Optional[str] = None  # optional hint για το ai_plan


class TenCommitIn(BaseModel):
    preview_id: Optional[str] = None
    preview_url: Optional[str] = None


def _base_url(req: Request) -> str:
    return f"{req.url.scheme}://{req.url.netloc}"


def _auth_header(req: Request) -> Dict[str, str]:
    auth = req.headers.get("authorization") or req.headers.get("Authorization")
    return {"Authorization": auth} if auth else {}


@router.post("/preview")
async def tengine_preview(req: Request, body: TenPreviewIn):
    """
    Proxy προς /previews/render, με extra επιλογή use_ai_plan.
    - Αν use_ai_plan=True → καλούμε το ai_plan, παίρνουμε mapping/caption
      και το περνάμε στο render.
    - Αν αποτύχει το ai_plan → fallback στο κανονικό payload.
    """
    base = _base_url(req)
    headers = {"Content-Type": "application/json", **_auth_header(req)}

    payload = body.model_dump(exclude_none=True)

    caption_from_ai = None

    if body.use_ai_plan:
        try:
            plan = ai_plan({
                "platform": body.platform or "instagram",
                "ratio": body.ratio or "4:5",
                "mode": body.mode or "normal",
                "product_url": body.product_url or body.image_url,
            })
            if plan and isinstance(plan, dict):
                if plan.get("mapping") and not body.mapping:
                    payload["mapping"] = plan["mapping"]
                caption_from_ai = plan.get("caption")
        except Exception as e:
            # δεν ρίχνουμε σφάλμα, συνεχίζουμε με fallback
            caption_from_ai = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base}/previews/render", headers=headers, json=payload)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"detail": r.text}
        raise HTTPException(status_code=r.status_code, detail=detail)

    resp = r.json()
    if caption_from_ai:
        resp["caption"] = caption_from_ai
    return resp


@router.post("/commit")
async def tengine_commit(req: Request, body: TenCommitIn):
    """
    Proxy προς /previews/commit.
    """
    base = _base_url(req)
    headers = {"Content-Type": "application/json", **_auth_header(req)}
    payload = body.model_dump(exclude_none=True)

    if not payload.get("preview_id") and not payload.get("preview_url"):
        raise HTTPException(status_code=422, detail="preview_url or preview_id is required")

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base}/previews/commit", headers=headers, json=payload)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"detail": r.text}
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()
