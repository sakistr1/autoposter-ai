# --- BEGIN PATCH ---
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
import httpx
import asyncio

# Σωστό import του ai_plan
from production_engine.routers.ai_plan import ai_plan

router = APIRouter(prefix="/tengine", tags=["tengine"])

# ---------- CONFIG ----------
HTTPX_TIMEOUT = httpx.Timeout(connect=3.0, read=20.0, write=10.0, pool=5.0)
HTTPX_LIMITS  = httpx.Limits(max_keepalive_connections=10, max_connections=20)
RETRY_ATTEMPTS = 2  # επιπλέον των 1ης προσπάθειας

class TenPreviewIn(BaseModel):
    platform: Optional[str] = None
    ratio: Optional[str] = None
    mode: Optional[str] = Field(default="normal")
    image_url: Optional[str] = None
    mapping: Optional[Dict[str, Any]] = None
    watermark: Optional[bool] = None
    return_absolute_url: Optional[bool] = True
    use_renderer: bool = False
    use_ai_plan: bool = False
    product_url: Optional[str] = None
    template_id: Optional[int] = None  # υπήρχε ήδη στο payload που στέλνουμε προς render

class TenCommitIn(BaseModel):
    preview_id: Optional[str] = None
    preview_url: Optional[str] = None

def _base_url(req: Request) -> str:
    return f"{req.url.scheme}://{req.url.netloc}"

def _auth_header(req: Request) -> Dict[str, str]:
    auth = req.headers.get("authorization") or req.headers.get("Authorization")
    return {"Authorization": auth} if auth else {}

async def _post_json_with_retry(url: str, headers: Dict[str, str], payload: Dict[str, Any]):
    """
    POST με μικρό retry μόνο για 5xx/timeout. Δεν επαναπροσπαθούμε για 4xx.
    """
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT, limits=HTTPX_LIMITS) as client:
        attempt = 0
        while True:
            try:
                r = await client.post(url, headers=headers, json=payload)
                # Retry μόνο για 5xx
                if r.status_code >= 500 and attempt < RETRY_ATTEMPTS:
                    attempt += 1
                    await asyncio.sleep(0.6 * attempt)
                    continue
                return r
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                if attempt < RETRY_ATTEMPTS:
                    attempt += 1
                    await asyncio.sleep(0.6 * attempt)
                    continue
                raise e

@router.post("/preview")
async def tengine_preview(req: Request, body: TenPreviewIn):
    """
    Proxy προς /previews/render, με:
    - 422 validation: αν use_renderer=True απαιτείται image_url
    - use_ai_plan flag: αν True, παράγουμε mapping/caption πριν το render
    - timeouts/retry στα internal HTTP
    """
    # ---- Validation (ρητό, μη διαπραγματεύσιμο) ----
    if body.use_renderer and not body.image_url:
        raise HTTPException(status_code=422, detail="image_url is required when use_renderer=true")

    base = _base_url(req)
    headers = {"Content-Type": "application/json", **_auth_header(req)}
    payload = body.model_dump(exclude_none=True)

    caption_from_ai: Optional[str] = None

    if body.use_ai_plan:
        try:
            plan = ai_plan({
                "platform": body.platform or "instagram",
                "ratio": body.ratio or "4:5",
                "mode": body.mode or "normal",
                "product_url": body.product_url or body.image_url,
                "image_url": body.image_url,
            })
            if isinstance(plan, dict):
                # αν δεν δόθηκε mapping, πάρε από ai_plan
                if plan.get("mapping") and not body.mapping:
                    payload["mapping"] = plan["mapping"]
                caption_from_ai = plan.get("caption")
        except Exception:
            # Δεν πέφτει ο endpoint· απλά συνεχίζουμε χωρίς caption/mapping
            caption_from_ai = None

    r = await _post_json_with_retry(f"{base}/previews/render", headers, payload)

    # Αν έχει λήξει token, δώσε καθαρό μήνυμα
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="Token expired – refresh")

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
    Proxy προς /previews/commit με timeouts/retry και καθαρό μήνυμα 401.
    """
    base = _base_url(req)
    headers = {"Content-Type": "application/json", **_auth_header(req)}
    payload = body.model_dump(exclude_none=True)

    if not payload.get("preview_id") and not payload.get("preview_url"):
        raise HTTPException(status_code=422, detail="preview_url or preview_id is required")

    r = await _post_json_with_retry(f"{base}/previews/commit", headers, payload)

    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="Token expired – refresh")

    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"detail": r.text}
        raise HTTPException(status_code=r.status_code, detail=detail)

    return r.json()
# --- END PATCH ---
