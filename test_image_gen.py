from PIL import Image, ImageDraw, ImageFont
import os

def create_post_with_caption(template_path, output_path, caption):
    # Φορτώνουμε το template PNG
    img = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Ρυθμίσεις γραμματοσειράς (βάλε το σωστό path της font που έχεις)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_title = ImageFont.truetype(font_path, 32)
    font_text = ImageFont.truetype(font_path, 18)

    # Θέσεις κειμένου (ρύθμισέ τες ανάλογα με το template σου)
    x, y = 100, 150

    # Τίτλος
    draw.text((x, y), "RUN WITH CONFIDENCE", font=font_title, fill="#333333")

    # Υπόλοιπο κείμενο
    y += 40
    draw.text((x, y), "Upgrade your running gear today!", font=font_text, fill="#333333")
    y += 25
    draw.text((x, y), "20% OFF on selected items.", font=font_text, fill="#333333")
    y += 25
    draw.text((x, y), "Visit sportpsd.com", font=font_text, fill="#333333")

    # Αποθήκευση
    img.save(output_path)
    print(f"Created post saved at {output_path}")

# Χρήση
create_post_with_caption(
    template_path="templates_images/4742764.png",
    output_path="output/post_example.png",
    caption=None  # Για τώρα δεν χρησιμοποιούμε παράμετρο caption γιατί είναι hardcoded εδώ
)
