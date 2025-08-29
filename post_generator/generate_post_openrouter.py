import openai
import base64
import os
from PIL import Image, ImageDraw, ImageFont

# ✅ Ρύθμιση API Key και OpenRouter endpoint
openai.api_key = os.getenv("OPENROUTER_API_KEY")
openai.base_url = "https://openrouter.ai/api/v1"

# 📸 Φόρτωσε την εικόνα
image_path = "test1.jpg"
with open(image_path, "rb") as f:
    image_bytes = f.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

# 🎯 Ανάλυση προϊόντος από την εικόνα με GPT-4o (OpenRouter)
response = openai.chat.completions.create(
    model="openai/gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "Είσαι ειδικός στο marketing ελληνικών e-shop. Δημιούργησε Instagram post για προϊόν από φωτογραφία."
        },
        {
            "role": "user",
            "content": "Ανάλυσε την παρακάτω εικόνα προϊόντος και δημιούργησε post με τίτλο, περιγραφή, emoji και hashtags. Γλώσσα: Ελληνικά.",
        },
        {
            "role": "user",
            "content": {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                    "detail": "low"
                }
            }
        }
    ],
    max_tokens=500
)

# 📄 Λήψη αποτελέσματος
caption = response.choices[0].message.content.strip()
print("📄 Generated Caption:\n")
print(caption)

# 🖼️ Δημιουργία τελικής εικόνας με το caption επάνω
img = Image.open(image_path)
draw = ImageDraw.Draw(img)
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # Ή άλλη κατάλληλη για Ελληνικά
font = ImageFont.truetype(font_path, 40)

text_position = (30, img.height - 200)
draw.text(text_position, caption.split('\n')[0], font=font, fill="white")

# 💾 Αποθήκευση τελικής εικόνας
output_path = "final_post.jpg"
img.save(output_path)
print(f"\n✅ Created image: {output_path}")
