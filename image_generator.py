# image_generator.py

from PIL import Image, ImageDraw, ImageFont
import requests
from BytesIO
import os

def generate_post_image(image_url, caption, output_path='static/post_image.jpg'):
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content)).convert("RGB")
    image = image.resize((800, 800))  # Τετράγωνο Instagram-style

    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 24)

    # Επαναφορά πολλαπλών γραμμών
    lines = caption.split("\n")
    y_text = 650
    for line in lines:
        draw.text((30, y_text), line, font=font, fill="white")
        y_text += 30

    os.makedirs("static", exist_ok=True)
    image.save(output_path)
    return output_path
