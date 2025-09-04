from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..engine_database import Base

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # image | carousel | video
    aspect_ratio = Column(String, nullable=True)  # π.χ. "1:1", "9:16"
    engine = Column(String, nullable=True)  # svg | moviepy
    preview_thumb_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    placeholders = relationship("TemplatePlaceholder", back_populates="template", cascade="all, delete-orphan")
