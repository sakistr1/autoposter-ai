from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from token_module import get_current_user
from database import get_db
from services.stripe_service import (
    create_checkout_session,
    cancel_user_subscription
)
from schemas import CreateCheckoutSessionRequest
from models import User

router = APIRouter()

@router.post("/subscribe")
def subscribe_to_plan(
    data: CreateCheckoutSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_url = create_checkout_session(current_user, data.plan_id, db)
    return {"checkout_url": session_url}

@router.get("/cancel-subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cancel_user_subscription(current_user, db)
    return RedirectResponse(url="/dashboard.html")
