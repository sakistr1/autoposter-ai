import base64
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL", "qwen/qwen3-8b:free")

def encode_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def generate_caption(image_b64):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",  # ή βάλε το domain σου
        "X-Title": "autoposter"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Είσαι ένας βοηθός που δημιουργεί έξυπνες λεζάντες για προϊόντα βάσει εικόνας."
            },
            {
                "role": "user",
                "content": f"Ανέλυσε αυτό το προϊόν και γράψε μια λεζάντα για Instagram:\n[Image (base64)]: {image_b64[:300]}..."  # δείγμα μόνο
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)

    print("🔁 Απάντηση από server:")
    print(response.status_code)
    print(response.text)

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def main():
    image_path = "input.jpg"

    print("🔍 Ανάλυση προϊόντος...")
    image_b64 = encode_image(image_path)
    try:
        caption = generate_caption(image_b64)
        print("📸 Λεζάντα εικόνας:")
        print(caption)
    except requests.exceptions.HTTPError as err:
        print("⚠️ Σφάλμα:", err)

if __name__ == "__main__":
    main()
