def plan_post(product: dict, user_opts: dict) -> dict:
    images = (user_opts.get("extra_images") or []) + product.get("images", [])
    if not images:
        images = ["/static/demo/outfit1.webp"]
    frames = [{"image": p} for p in images[:3]]

    return {
        "template_id": "clean_card",
        "aspect": "1:1",
        "primary_color": "#121216",
        "accent_color": "#EA4335",
        "caption_title": product.get("title", ""),
        "caption_price": product.get("price", ""),
        "discount_percent": product.get("discount_percent"),
        "brand": product.get("brand", ""),
        "logo": "/static/logo.png",
        "frames": frames,
        "duration_sec": 10,
        "fps": 30,
        "music_bucket": "ambient"
    }
