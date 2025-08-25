from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import stripe
from decouple import config
from models import User
from token_module import get_current_user
from database import get_db

router = APIRouter()

# Φόρτωση του Stripe secret key από το .env
stripe_api_key = config("STRIPE_SECRET_KEY")
print(f"[DEBUG] Loaded Stripe Secret Key: {stripe_api_key[:10]}...")  # Μόνο πρώτα 10 chars για ασφάλεια
stripe.api_key = stripe_api_key

class SubscribeInput(BaseModel):
    plan_id: str

class CreditsInput(BaseModel):
    credits: int

@router.post("/subscribe")
def subscribe(
    input_data: SubscribeInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # Debug print για το κλειδί και χρήστη κάθε φορά που καλείται
        print(f"[DEBUG subscribe] Stripe key at call time: {config('STRIPE_SECRET_KEY')[:10]}...")
        print(f"[DEBUG subscribe] plan_id={input_data.plan_id}, user={current_user.email}")
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": input_data.plan_id,
                "quantity": 1,
            }],
            success_url=config("FRONTEND_BASE_URL") + "?success=true&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=config("FRONTEND_BASE_URL") + "?canceled=true",
            customer_email=current_user.email,
        )
        print(f"[DEBUG subscribe] checkout session created: {session.id}")
        return JSONResponse({"checkout_url": session.url})
    except stripe.error.StripeError as e:
        print(f"[ERROR subscribe] {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/buy-credits")
def buy_credits(
    input_data: CreditsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        credits_price_id = config("STRIPE_CREDITS_PRICE_ID")
        print(f"[DEBUG buy_credits] credits={input_data.credits}, price_id={credits_price_id}, user={current_user.email}")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price": credits_price_id,
                "quantity": 1,
            }],
            success_url=config("FRONTEND_BASE_URL") + "?success=true&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=config("FRONTEND_BASE_URL") + "?canceled=true",
            customer_email=current_user.email,
            metadata={"user_id": current_user.id, "credits": input_data.credits}
        )
        print(f"[DEBUG buy_credits] checkout session created: {session.id}")
        return JSONResponse({"checkout_url": session.url})
    except stripe.error.StripeError as e:
        print(f"[ERROR buy_credits] {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/cancel-subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        print(f"[DEBUG cancel_subscription] user={current_user.email}")
        # TODO: Αποθήκευση και χρήση subscription_id στον χρήστη για να γίνει ακύρωση
        raise HTTPException(status_code=501, detail="Cancellation not implemented yet")
    except Exception as e:
        print(f"[ERROR cancel_subscription] {e}")
        raise
