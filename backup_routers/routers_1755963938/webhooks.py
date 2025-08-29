# backend/routers/webhooks.py

import os
import json
import stripe
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Χάρτης plan → credits
PLAN_CREDITS = {
    "basic": 20,
    "premium": 50,
    "pro": 100,
}

@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    print(f"📩 Stripe webhook received: {event['type']}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        subscription_plan = session.get("metadata", {}).get("plan")

        print(f"➡️ Email: {customer_email}, Plan: {subscription_plan}")

        if not customer_email or not subscription_plan:
            print("⚠️ Missing metadata or email")
            return {"status": "ignored - missing metadata or email"}

        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            print("⚠️ User not found in database")
            return {"status": "ignored - user not found"}

        credits_to_add = PLAN_CREDITS.get(subscription_plan)
        if not credits_to_add:
            print(f"⚠️ Unknown plan: {subscription_plan}")
            return {"status": "ignored - unknown plan"}

        user.credits += credits_to_add
        db.commit()
        print(f"✅ Added {credits_to_add} credits to user {user.email}")

    return {"status": "success"}
