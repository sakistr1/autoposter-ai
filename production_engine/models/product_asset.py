from sqlalchemy import Column, Integer, String, ForeignKey
from ..engine_database import Base

class ProductAsset(Base):
    __tablename__ = "product_assets"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, nullable=False)  # προς products στο main project (για αργότερα)
    image_url = Column(String, nullable=False)
    kind = Column(String, default="extra")  # main | extra
    sort_order = Column(Integer, default=0)
