import random
from typing import Optional, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

# --------------------------
# Core mock planner function
# --------------------------
def ai_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    captions = [
        "🔥 Νέο προϊόν σε προσφορά!",
        "✨ Κάνε level-up στο στυλ σου!",
        "⚡ Μην χάσεις αυτή την ευκαιρία!",
        "🎯 Το χρειάζεσαι σήμερα!",
        "💎 Premium ποιότητα, μοναδική τιμή!"
    ]
    caption = random.choice(captions)

    ctas = ["Αγόρασέ το", "Δες περισσότερα", "Κάνε το δικό σου", "Shop Now"]
    mapping = {
        "title": "DEMO AUTO-PLAN",
        "price": "€29,90",
        "old_price": "€39,90",
        "discount_badge": "-25%",
        "cta": random.choice(ctas),
        "title_color": "#ffffff",
        "price_color": "#00d084",
        "cta_bg": "#111827",
        "cta_text": "#ffffff",
        "overlay_rgba": "0,0,0,150"
    }

    preview_payload = {
        "mapping": mapping,
        "use_renderer": True,
        "watermark": True,
        "ratio": params.get("ratio") or "4:5"
    }

    return {
        "caption": caption,
        "mapping": mapping,
        "preview_payload": preview_payload
    }

# --------------------------
# FastAPI router (for /ai/plan)
# --------------------------
router = APIRouter()

class PlanIn(BaseModel):
    platform: Optional[str] = "instagram"
    ratio: Optional[str] = "4:5"
    mode: Optional[str] = "normal"
    product_url: Optional[str] = None
    image_url: Optional[str] = None

@router.post("/plan")
def plan_endpoint(body: PlanIn):
    """HTTP endpoint: returns the same structure as ai_plan()."""
    return ai_plan(body.model_dump())
