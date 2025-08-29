from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

try:
    from database import Base
except ImportError:
    from backend.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    image_url = Column(String)
    available = Column(Boolean, default=True)
    categories = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))

    price = Column(String, nullable=True)  # <-- Προσθήκη πεδίου τιμής

    owner = relationship("User", back_populates="products")
    posts = relationship("Post", back_populates="product", cascade="all, delete-orphan")
