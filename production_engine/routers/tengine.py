from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
import httpx

router = APIRouter(prefix="/tengine", tags=["tengine"])

class TenPreviewIn(BaseModel):
    platform: Optional[str] = None
    ratio: Optional[str] = None
    mode: Optional[str] = Field(default="normal")
    image_url: Optional[str] = None
    mapping: Optional[Dict[str, Any]] = None
    watermark: Optional[bool] = None
    return_absolute_url: Optional[bool] = True

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
    base = _base_url(req)
    headers = {"Content-Type": "application/json", **_auth_header(req)}
    payload = body.model_dump(exclude_none=True)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base}/previews/render", headers=headers, json=payload)
    if r.status_code >= 400:
        try: detail = r.json()
        except Exception: detail = {"detail": r.text}
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()

@router.post("/commit")
async def tengine_commit(req: Request, body: TenCommitIn):
    base = _base_url(req)
    headers = {"Content-Type": "application/json", **_auth_header(req)}
    payload = body.model_dump(exclude_none=True)

    if not payload.get("preview_id") and not payload.get("preview_url"):
        raise HTTPException(status_code=422, detail="preview_url or preview_id is required")

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base}/previews/commit", headers=headers, json=payload)
    if r.status_code >= 400:
        try: detail = r.json()
        except Exception: detail = {"detail": r.text}
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r.json()
