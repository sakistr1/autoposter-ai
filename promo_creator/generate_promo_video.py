from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import os

def generate_promo_video(product_name, price, image_path, logo_path=None, output_path="promo_video.mp4"):
    # Ρυθμίσεις
    width, height = 1080, 1080
    background_color = (20, 20, 20)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    
    # Δημιουργία background εικόνας
    img = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(img)
    
    # Φόρτωση γραμματοσειράς με υποστήριξη ελληνικών
    font_title = ImageFont.truetype(font_path, 60)
    font_price = ImageFont.truetype(font_path, 48)
    font_cta = ImageFont.truetype(font_path, 40)
    
    # Σχεδίαση τίτλου
    draw.text((50, 50), product_name, font=font_title, fill="white")
    
    # Σχεδίαση τιμής
    draw.text((50, 140), f"Τιμή: {price}€", font=font_price, fill="yellow")

    # Σχεδίαση CTA
    draw.text((50, 220), "Αγόρασέ το τώρα! 👉", font=font_cta, fill="lightgreen")

    # Αποθήκευση προσωρινής εικόνας
    temp_img_path = "temp_promo_image.jpg"
    img.save(temp_img_path)

    # Δημιουργία video από εικόνα
    clip = ImageClip(temp_img_path).set_duration(5)

    # Προσθήκη μουσικής (προαιρετικά)
    # audio = AudioFileClip("music.mp3").subclip(0, 5)
    # clip = clip.set_audio(audio)

    # Τελική απόδοση
    clip.write_videofile(output_path, fps=24)

    # Καθαρισμός
    os.remove(temp_img_path)
    print(f"✅ Promo video saved as {output_path}")

# Δοκιμή
if __name__ == "__main__":
    generate_promo_video(
        product_name="Μπλούζα Ανδρική",
        price="19.90",
        image_path="test1.jpg",
        logo_path=None
    )
