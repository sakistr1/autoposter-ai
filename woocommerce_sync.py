# backend/woocommerce_sync.py

import requests
from models.product import Product

def fetch_and_store_products_from_woocommerce(db, woocommerce_url, consumer_key, consumer_secret, owner_id):
    url = f"{woocommerce_url}/wp-json/wc/v3/products"
    try:
        response = requests.get(url, auth=(consumer_key, consumer_secret))
        response.raise_for_status()
    except Exception as e:
        raise Exception(f"Σφάλμα κατά το fetch από WooCommerce: {e}")

    products_data = response.json()
    product_objects = []

    for item in products_data:
        product = Product(
            name=item.get("name", "Χωρίς Όνομα"),
            description=item.get("description", ""),
            image_url=item.get("images", [{}])[0].get("src", ""),
            owner_id=owner_id
        )
        db.add(product)
        product_objects.append(product)

    db.commit()
    return product_objects
