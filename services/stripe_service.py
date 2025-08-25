import os
import stripe
from fastapi import HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def create_checkout_session(user, plan_id: str):
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": plan_id,
                "quantity": 1,
            }],
            success_url=os.getenv("FRONTEND_BASE_URL") + "?success=true&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=os.getenv("FRONTEND_BASE_URL") + "?canceled=true",
            customer_email=user.email,
            metadata={"user_id": user.id}
        )
        return checkout_session.url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def cancel_user_subscription(user):
    try:
        if not user.stripe_subscription_id:
            return False
        stripe.Subscription.delete(user.stripe_subscription_id)
        return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def create_credits_checkout_session(user, credits: int):
    try:
        price_id = os.getenv("STRIPE_CREDITS_PRICE_ID")
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price": price_id,
                "quantity": credits,
            }],
            success_url=os.getenv("FRONTEND_BASE_URL") + "?success=true&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=os.getenv("FRONTEND_BASE_URL") + "?canceled=true",
            customer_email=user.email,
            metadata={
                "user_id": user.id,
                "credits": credits
            }
        )
        return checkout_session.url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
