import os

def generate_post_text(product_name: str, product_description: str):
    # Αν δεν έχει OpenAI API Key, γύρνα dummy post
    if not os.getenv("OPENAI_API_KEY"):
        return f"📢 Νέο προϊόν: {product_name} – {product_description[:60]}..."

    # TODO: Προσθήκη GPT integration εδώ (όταν έχεις key)
    return f"🚀 Δες το νέο μας προϊόν: {product_name} – {product_description[:60]}..."
