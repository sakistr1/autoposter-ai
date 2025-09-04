import google.generativeai as genai

# Βάλε εδώ το API key σου
API_KEY = "AIzaSyDGGv9zzGY3l5BS7u3UYcVfulVxZiT1hUc"

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

def generate_caption(description):
    prompt = f"""
    Δημιούργησε έξυπνη και πιασάρικη λεζάντα Instagram για αυτό το προϊόν:
    Περιγραφή: {description}

    Η λεζάντα να είναι σύντομη, μοντέρνα και να περιλαμβάνει hashtags.
    """
    response = model.generate_content(prompt)
    return response.text.strip()

if __name__ == "__main__":
    description = input("📝 Περιγραφή προϊόντος: ")
    print("📸 Δημιουργία λεζάντας...")
    try:
        caption = generate_caption(description)
        print("\n✅ Λεζάντα:\n")
        print(caption)
    except Exception as e:
        print(f"⚠️ Σφάλμα: {e}")
