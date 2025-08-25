import os
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.VideoClip import TextClip
from models.product import Product  # ΣΩΣΤΟ import

STATIC_DIR = "backend/static/ads"

def _create_image(product: Product, filename: str, suffix: str = "") -> str:
    os.makedirs(STATIC_DIR, exist_ok=True)
    img = Image.new('RGB', (600, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    lines = [
        product.name or "Product",
        f"{product.price:.2f} €" if getattr(product, "price", None) else "",
        product.description or "",
        suffix
    ]
    y = 50
    for line in lines:
        if line:
            draw.text((30, y), line, font=font, fill=(0, 0, 0))
            y += 50

    filepath = os.path.join(STATIC_DIR, filename)
    img.save(filepath)
    return f"/static/ads/{filename}"

def generate_ad_content(product: Product, post_type: str) -> str:
    if post_type != "image":
        raise ValueError("Only 'image' post_type supported in generate_ad_content.")
    filename = f"ad_{product.id}.png"
    return _create_image(product, filename)

def generate_carousel_images(product: Product, count: int = 3) -> list[str]:
    urls = []
    for i in range(1, count + 1):
        filename = f"ad_{product.id}_{i}.png"
        suffix = f"Slide {i}"
        url = _create_image(product, filename, suffix=suffix)
        urls.append(url)
    return urls

def generate_video_ad(product: Product) -> str:
    os.makedirs(STATIC_DIR, exist_ok=True)

    text = f"{product.name or 'Product'}\n"
    if getattr(product, "price", None):
        text += f"{product.price:.2f} €\n"
    if getattr(product, "description", None):
        text += product.description

    clip = TextClip(text, fontsize=24, color='white', size=(600, 400), method='caption')
    clip = clip.set_duration(5).set_position('center').on_color(color=(0, 0, 0), col_opacity=1)

    video_filename = f"ad_{product.id}.mp4"
    video_path = os.path.join(STATIC_DIR, video_filename)
    clip.write_videofile(video_path, fps=24, codec="libx264", audio=False, logger=None)
    clip.close()

    return f"/static/ads/{video_filename}"

def generate_mock_post(product_name: str, post_type: str) -> list[str]:
    if post_type == "image":
        return [f"https://via.placeholder.com/600x600?text={product_name.replace(' ', '+')}"]
    elif post_type == "carousel":
        return [
            f"https://via.placeholder.com/600x600?text={product_name}+1",
            f"https://via.placeholder.com/600x600?text={product_name}+2",
            f"https://via.placeholder.com/600x600?text={product_name}+3"
        ]
    elif post_type == "video":
        return [f"https://example.com/mock_video_for_{product_name}.mp4"]
    else:
        return []
