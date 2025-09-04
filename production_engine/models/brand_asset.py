from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from ..engine_database import Base

class BrandAsset(Base):
    __tablename__ = "brand_assets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # προς users στο main project (για αργότερα)
    logo_url = Column(String, nullable=True)
    palette = Column(JSON, nullable=True)  # {"primary": "#FF0000", "secondary": "#000000"}
