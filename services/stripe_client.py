import os
import stripe
from dotenv import load_dotenv

load_dotenv()  # Φορτώνει τις μεταβλητές από το .env

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = STRIPE_SECRET_KEY

def create_payment_intent(amount_cents: int, currency: str = "eur"):
    """
    Δημιουργεί ένα payment intent στο Stripe.
    amount_cents: ποσό σε cents (π.χ. 100 = 1 ευρώ)
    currency: νόμισμα, default ευρώ
    """
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            payment_method_types=["card"],
        )
        return intent
    except Exception as e:
        print(f"Stripe create_payment_intent error: {e}")
        raise e
