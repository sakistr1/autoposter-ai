from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from ..engine_database import Base

class CommittedPost(Base):
    __tablename__ = "committed_posts"

    id = Column(Integer, primary_key=True, index=True)
    preview_id = Column(String, nullable=False, index=True)
    urls_json = Column(Text, nullable=False)  # JSON string με τη λίστα των URLs (images/mp4)
    created_at = Column(DateTime, default=datetime.utcnow)
