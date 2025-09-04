def fetch_product_by_url(url: str) -> dict:
    # Placeholder: δεν κάνει requests ακόμα (θα το βάλουμε αργότερα).
    return {
        "id": url,
        "url": url,
        "title": "Untitled",
        "price": "",
        "discount_percent": None,
        "brand": "",
        "images": [],   # θα γεμίσει από extra_images ή default demo
        "currency": "EUR",
    }
