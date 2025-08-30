# production_engine/routers/ai_plan.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl
from typing import Literal, Dict, Any
from urllib.parse import urlparse
from token_module import get_current_user
from models.user import User

router = APIRouter()

# Είσοδος/Έξοδος
Platform = Literal["facebook", "instagram", "tiktok", "linkedin"]
Ratio = Literal["1:1", "4:5", "9:16"]
ModeIn = Literal["κανονικό", "χιουμοριστικό", "επαγγελματικό", "normal"]  # δέχομαι και ελληνικά

class AIPlanIn(BaseModel):
    product_url: HttpUrl
    platform: Platform
    ratio: Ratio
    mode: ModeIn

class AIPlanOut(BaseModel):
    template_id: int
    caption: str
    mapping: Dict[str, Any]
    preview_payload: Dict[str, Any]

# -------- Helpers (ωμά και σταθερά) --------
LOCAL_FALLBACK = "http://127.0.0.1:8000/static/uploads/placeholder.png"  # ΠΡΕΠΕΙ να υπάρχει

def _pick_template_id(platform: str, ratio: str) -> int:
    table = {
        ("instagram", "4:5"): 1,
        ("instagram", "1:1"): 2,
        ("tiktok", "9:16"):   3,
        ("facebook", "1:1"):  4,
        ("linkedin", "1:1"):  5,
    }
    return table.get((platform, ratio), 1)

def _normalize_mode(mode: str) -> str:
    # Το render σου υποστηρίζει "normal". Οτιδήποτε άλλο → "normal"
    return "normal"

def _caption(mode: str, platform: str) -> str:
    base = "Δες την προσφορά τώρα!"
    hashtag = {
        "instagram": "#instadeals",
        "facebook": "#offers",
        "tiktok": "#fyp",
        "linkedin": "#business",
    }[platform]
    return f"{base} {hashtag}"

def _mapping(product_url: str, image_url: str) -> Dict[str, Any]:
    host = urlparse(product_url).netloc or "site"
    return {
        "title": f"Προσφορά από {host}",
        "price": "€19.90",
        "old_price": "€24.90",
        "discount_badge": "-20%",
        "image_url": image_url,  # και μέσα στο mapping
        "cta": "Αγόρασε τώρα",
    }

@router.post("/plan", response_model=AIPlanOut)
def ai_plan(b: AIPlanIn, current_user: User = Depends(get_current_user)):
    template_id = _pick_template_id(b.platform, b.ratio)
    mode = _normalize_mode(b.mode)
    image_url = LOCAL_FALLBACK  # δεν κάνουμε outbound HTTP, πάντα παίζει
    caption = _caption(mode, b.platform)
    mapping = _mapping(str(b.product_url), image_url)

    # PAYLOAD που θέλει το /previews/render (root image_url + mapping + mode normal)
    preview_payload = {
        "template_id": template_id,
        "ratio": b.ratio,
        "platform": b.platform,
        "mode": mode,
        "image_url": image_url,       # ΑΠΑΡΑΙΤΗΤΟ στο root
        "mapping": mapping,           # και μέσα στο mapping
        "watermark": True,
        "return_absolute_url": True,
    }

    return AIPlanOut(
        template_id=template_id,
        caption=caption,
        mapping=mapping,
        preview_payload=preview_payload,
    )
