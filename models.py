from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    woocommerce_url = Column(String, nullable=True)
    consumer_key = Column(String, nullable=True)
    consumer_secret = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True)  # ✅ Προστέθηκε

    products = relationship("Product", back_populates="owner")
    posts = relationship("Post", back_populates="owner")
    templates = relationship("Template", back_populates="owner")  # Νέο

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    price = Column(String, nullable=True)
    permalink = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="products")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    type = Column(String, nullable=False)  # image, carousel, video
    media_urls = Column(String, nullable=True)  # stored as JSON string
    caption = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="posts")

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # image, carousel, video
    file_path = Column(String, nullable=False)  # path ή url του template αρχείου
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Αν θες templates ανά χρήστη

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="templates")
