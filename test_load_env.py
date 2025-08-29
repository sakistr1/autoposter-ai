from decouple import config
import stripe

def main():
    stripe_key = config("STRIPE_SECRET_KEY")
    print(f"[TEST] Loaded Stripe Secret Key: {stripe_key[:10]}...")

    stripe.api_key = stripe_key

    try:
        balance = stripe.Balance.retrieve()
        print("[TEST] Stripe balance retrieved successfully!")
        print(balance)
    except Exception as e:
        print(f"[TEST ERROR] Stripe API call failed: {e}")

if __name__ == "__main__":
    main()
