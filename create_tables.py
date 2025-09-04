from database import Base, engine

# Αυτό το import είναι απαραίτητο για να "φορτωθούν" τα models
from models.user import User
from models.product import Product
from models.post import Post

print("Database URL:", engine.url)
print("Models loaded:")
print(User)
print(Product)
print(Post)

print("✅ Creating tables...")
Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully.")
