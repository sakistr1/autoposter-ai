# routers/templates.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from token_module import get_current_user
from models import User
from database import get_db

# Δώσε το σωστό import ανάλογα με το path σου:
try:
    from services.template_registry import REGISTRY
except Exception:
    from production_engine.services.template_registry import REGISTRY  # fallback αν τα έχεις αλλιώς

router = APIRouter(prefix="/templates", tags=["templates"])

@router.get("")
def list_templates(current_user: User = Depends(get_current_user)):
    """Επιστρέφει λίστα templates (id, name, ratios, fields, thumb)."""
    return REGISTRY.list()

@router.get("/{template_id}")
def get_template(template_id: str, current_user: User = Depends(get_current_user)):
    """Επιστρέφει το πλήρες meta.json ενός template."""
    try:
        meta = REGISTRY.detail(template_id)
        return meta
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")

@router.post("/reload")
@router.get("/reload")
def reload_templates(current_user: User = Depends(get_current_user)):
    """
    File-based registry: δεν χρειάζεται πραγματικό reload.
    Δίνουμε count ως health check.
    """
    items = REGISTRY.list()
    return {"ok": True, "count": len(items)}
