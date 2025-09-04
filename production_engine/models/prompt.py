from sqlalchemy import Column, Integer, String, Text
from ..engine_database import Base

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    post_type = Column(String, nullable=False)  # image | carousel | video
    mode = Column(String, nullable=False)  # normal | funny | pro | romantic | aggressive
    text_template = Column(Text, nullable=False)  # Jinja2 prompt text
