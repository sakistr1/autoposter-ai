# services/image_generation.py
from PIL import Image, ImageDraw, ImageFont
import os

TEMPLATES_DIR = "templates_images/"

def load_template(template_name: str) -> Image.Image:
    path = os.path.join(TEMPLATES_DIR, template_name)
    img = Image.open(path).convert("RGBA")
    return img

def add_caption(img: Image.Image, text: str, position=(10, 10), font_path=None, font_size=24, color=(255, 255, 255)) -> Image.Image:
    draw = ImageDraw.Draw(img)
    try:
        if font_path and os.path.isfile(font_path):
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    draw.text(position, text, font=font, fill=color)
    return img

def create_image_post(template_name: str, caption: str, output_path: str, font_path=None, font_size=24):
    img = load_template(template_name)
    img = add_caption(img, caption, position=(20, 20), font_path=font_path, font_size=font_size)
    img.save(output_path)

def create_carousel_post(template_names: list[str], captions: list[str], output_dir: str, font_path=None, font_size=24) -> list[str]:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_paths = []
    for i, (template_name, caption) in enumerate(zip(template_names, captions)):
        img = load_template(template_name)
        img = add_caption(img, caption, position=(20, 20), font_path=font_path, font_size=font_size)
        output_path = os.path.join(output_dir, f"carousel_{i+1}.png")
        img.save(output_path)
        output_paths.append(output_path)
    return output_paths
