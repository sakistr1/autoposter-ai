import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime

# ΕΥΕΛΙΚΤΟ import για Base ώστε να δουλεύει σε Alembic & FastAPI
try:
    from database import Base
except ImportError:
    from backend.database import Base

class PostTypeEnum(enum.Enum):
    image = "image"
    carousel = "carousel"
    video = "video"

class PostStatusEnum(enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    content = Column(String, nullable=False)

    # Μόνο το owner_id για ξένο κλειδί προς users
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    type = Column(Enum(PostTypeEnum), nullable=False, default=PostTypeEnum.image)
    suggested_type = Column(Enum(PostTypeEnum), nullable=True)
    status = Column(Enum(PostStatusEnum), default=PostStatusEnum.pending)
    media_urls = Column(Text, nullable=True)  # π.χ. JSON string με URLs

    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="posts", foreign_keys=[owner_id])
    product = relationship("Product", back_populates="posts")
