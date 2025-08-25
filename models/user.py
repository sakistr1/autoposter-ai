from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    woocommerce_url = Column(String, nullable=True)
    consumer_key = Column(String, nullable=True)
    consumer_secret = Column(String, nullable=True)
    credits = Column(Integer, default=0)
    sync_url = Column(String, nullable=True)

    # Σχέσεις με string ονόματα για αποφυγή κυκλικών imports
    templates = relationship("Template", back_populates="owner", cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
