from sqlalchemy import Column, Integer, String, ForeignKey
from ..engine_database import Base

class MappingRule(Base):
    __tablename__ = "mapping_rules"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    post_type = Column(String, nullable=False)
    prompt_id = Column(Integer, ForeignKey("prompts.id"))
    template_id = Column(Integer, ForeignKey("templates.id"))
    weight = Column(Integer, default=1)
