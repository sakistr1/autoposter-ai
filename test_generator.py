from services.generator import generate_ad_content, generate_carousel_images, generate_video_ad
from models import Product

# Δημιουργία mock Product αντικειμένου (χωρίς βάση δεδομένων)
product = Product(id=123, name="Test Product", price=19.99, description="This is a test product")

print("Generating single image ad...")
img_url = generate_ad_content(product, post_type="image")
print("Image URL:", img_url)

print("Generating carousel images...")
carousel_urls = generate_carousel_images(product, count=3)
print("Carousel URLs:", carousel_urls)

print("Generating video ad (this may take a few seconds)...")
video_url = generate_video_ad(product)
print("Video URL:", video_url)
