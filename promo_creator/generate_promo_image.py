from PIL import Image, ImageDraw, ImageFont
import requests
from BytesIO

def generate_promo_image(title, price, image_url, output_path="promo_output.jpg"):
    # Φόρτωση εικόνας από URL ή τοπικό αρχείο
    if image_url.startswith("file://"):
        image_path = image_url.replace("file://", "")
        base_image = Image.open(image_path).convert("RGBA")
    else:
        response = requests.get(image_url)
        base_image = Image.open(BytesIO(response.content)).convert("RGBA")

    # Δημιουργία καμβά με επιπλέον ύψος για κείμενο
    width, height = base_image.size
    canvas = Image.new("RGBA", (width, height + 100), (255, 255, 255, 255))
    canvas.paste(base_image, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # Φόρτωση γραμματοσειρών
    try:
        font_title = ImageFont.truetype("arial.ttf", 30)
        font_price = ImageFont.truetype("arial.ttf", 40)
    except:
        font_title = ImageFont.load_default()
        font_price = ImageFont.load_default()

    # Προσθήκη τίτλου προϊόντος
    draw.text((10, height + 10), title, fill="black", font=font_title)

    # Προσθήκη τιμής
    draw.text((10, height + 50), f"{price:.2f}€", fill="red", font=font_price)

    # Αποθήκευση τελικής εικόνας
    canvas.convert("RGB").save(output_path)
    print(f"✅ Promo image saved as {output_path}")
