
from moviepy.editor import ImageClip, TextClip, CompositeVideoClip
from PIL import Image
import os

def generate_promo_video(product_image, title, description, logo_path, cta_text, output_path, hashtags):
    # Load product image and resize
    background = ImageClip(product_image).resize(height=720)

    # Logo
    logo = ImageClip(logo_path).resize(height=100).set_position(("right", "top")).set_duration(6)

    # Title
    title_txt = TextClip(title, fontsize=60, color='white', font='DejaVu-Bold')
    title_txt = title_txt.set_position(("center", 100)).set_duration(6)

    # Description
    desc_txt = TextClip(description, fontsize=35, color='white', font='DejaVu-Sans')
    desc_txt = desc_txt.set_position(("center", 200)).set_duration(6)

    # CTA + Hashtags
    cta_txt = TextClip(f"{cta_text}\n{hashtags}", fontsize=30, color='yellow', font='DejaVu-Sans')
    cta_txt = cta_txt.set_position(("center", 550)).set_duration(6)

    # Combine
    video = CompositeVideoClip([background.set_duration(6), logo, title_txt, desc_txt, cta_txt])
    video.write_videofile(output_path, fps=24)
