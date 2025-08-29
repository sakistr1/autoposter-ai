import google.generativeai as genai
from PIL import Image

# Βάλε εδώ το API key σου
genai.configure(api_key="AIzaSyDGGv9zzGY3l5BS7u3UYcVfulVxZiT1hUc")

# Φόρτωσε το μοντέλο Gemini Pro Vision
model = genai.GenerativeModel("gemini-1.5-flash")

# Άνοιξε την εικόνα
image_path = "input.jpg"
img = Image.open(image_path)

# Prompt προς το AI
prompt = "Γράψε μου μια έξυπνη και πιασάρικη λεζάντα Instagram για το προϊόν στην εικόνα"

# Στείλε εικόνα + prompt στο API
response = model.generate_content([img, prompt])

# Εκτύπωσε την απάντηση
print("📸 Λεζάντα:")
print(response.text)
