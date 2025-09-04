from database import Base, engine
from models import User, Product, Post

print("Models imported successfully.")

Base.metadata.create_all(bind=engine)

print("Database tables created.")
