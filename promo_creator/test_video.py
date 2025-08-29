from generate_promo_video import generate_promo_video

product = {
    "title": "Ακουστικά Bluetooth",
    "price": 24.99,
    "image_url": "file://product.jpg"  # Χρησιμοποιεί τοπική εικόνα
}

generate_promo_video(product["title"], product["price"], product["image_url"])
