from generate_promo_image import generate_promo_image

product = {
    "title": "Ασύρματα Ακουστικά Bluetooth",
    "price": 29.99,
    "image_url": "file://product.jpg"
}

generate_promo_image(product["title"], product["price"], product["image_url"])
