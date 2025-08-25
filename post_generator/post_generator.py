import google.generativeai as genai
import os
from PIL import Image

# 🔑 Βάλε εδώ το API KEY
GOOGLE_API_KEY = "AIzaSyDGGv9zzGY3l5BS7u3UYcVfulVxZiT1hUc"
genai.configure(api_key=GOOGLE_API_KEY)

# 🔧 Επέλεξε μοντέλο
model = genai.GenerativeModel(model_name="gemini-1.5-pro-vision")

# 📤 Φόρτωσε την εικόνα
def load_image(path):
    return Image.open(path)

image_path = "product.jpg"
try:
    img = load_image(image_path)
except Exception as e:
    print(f"⚠️ Σφάλμα φόρτωσης εικόνας: {e}")
    exit()

# 📝 Πρόσθεσε περιγραφή
user_input = input("📝 Προσθέστε σύντομη περιγραφή προϊόντος (ή Enter): ")

prompt = (
    f"Δώσε μου 3 έξυπνες και σύντομες λεζάντες Instagram για το εξής προϊόν: {user_input}. "
    "Χρησιμοποίησε μοντέρνο και ελκυστικό ύφος, ελληνικά hashtags και στυλ marketing."
)

# 📸 Ζήτα από το μοντέλο να απαντήσει
print("📸 Δημιουργία λεζάντας...")

try:
    response = model.generate_content(
        [prompt, img],
        generation_config={"temperature": 0.7}
    )
    caption = response.text
    print("\n📣 Λεζάντα:\n", caption)

    with open("caption_output.txt", "w", encoding="utf-8") as f:
        f.write(caption)

    print("✅ Αποθηκεύτηκε σε caption_output.txt")
except Exception as e:
    print(f"⚠️ Σφάλμα: {e}")
