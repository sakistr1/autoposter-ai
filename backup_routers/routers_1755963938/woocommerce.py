# routers/woocommerce.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from token_module import get_current_user
from schemas import WooCommerceCredentials

router = APIRouter(prefix="/me", tags=["woocommerce"])

@router.get("/woocommerce-credentials")
def get_woo_creds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "woocommerce_url": current_user.woocommerce_url,
        "consumer_key": current_user.consumer_key,
        "consumer_secret": current_user.consumer_secret,
        "sync_url": getattr(current_user, "sync_url", None),
    }

@router.post("/woocommerce-credentials")
def set_woo_creds(
    payload: WooCommerceCredentials,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.woocommerce_url or not payload.consumer_key or not payload.consumer_secret:
        raise HTTPException(status_code=400, detail="All fields required")

    current_user.woocommerce_url = payload.woocommerce_url.strip()
    current_user.consumer_key = payload.consumer_key.strip()
    current_user.consumer_secret = payload.consumer_secret.strip()
    if hasattr(current_user, "sync_url"):
        current_user.sync_url = payload.sync_url

    db.add(current_user)
    db.commit()
    return {"ok": True}
