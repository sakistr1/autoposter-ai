import json
from pathlib import Path
from PIL import Image
from services.products import fetch_product_by_url
from services.ai_planner import plan_post
from production_engine.templates.simple import render_frame

def first_existing_path(p: str) -> Path:
    pth = Path(p)
    if pth.exists(): return pth
    if p.startswith("/"):
        p2 = Path("." + p)  # π.χ. "/static/..." -> "./static/..."
        if p2.exists(): return p2
    return pth

def main():
    # Demo input: χωρίς network για αρχή
    product = {
        "id":"demo",
        "url":"",
        "title":"Outfit Black",
        "price":"149,00 €",
        "discount_percent":20,
        "brand":"Demo",
        "images":[]
    }
    user_opts = {
        "platform":"instagram",
        "mode":"static",
        "tone":"clean",
        "extra_images":["/static/demo/outfit1.webp"]  # τοπικό demo asset
    }

    spec = plan_post(product, user_opts)
    print(json.dumps(spec, ensure_ascii=False, indent=2))

    img_path = spec["frames"][0]["image"]
    fs_path = first_existing_path(img_path)
    with Image.open(fs_path) as im:
        out = render_frame(
            im,
            title=spec["caption_title"],
            price=spec["caption_price"],
            discount=spec.get("discount_percent"),
            brand=spec.get("brand")
        )
        out_path = Path("static/generated/ai_plan_demo_preview.webp")
        out.save(out_path)
        print(f"\nPreview saved → {out_path}")

if __name__ == "__main__":
    main()
