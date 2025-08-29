# models/user.py
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    credits = Column(Integer, default=0)

    # Template.owner  <->  User.templates
    templates = relationship(
        "Template",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # Product.owner  <->  User.products
    products = relationship(
        "Product",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # Post.owner  <->  User.posts
    posts = relationship(
        "Post",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # CreditTransaction.user  <->  User.credit_transactions
    credit_transactions = relationship(
        "CreditTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
