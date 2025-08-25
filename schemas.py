from pydantic import BaseModel, HttpUrl, EmailStr
from typing import List, Optional, Any, Dict, Union
from datetime import datetime


# ----------------- Woo / Billing -----------------

class WooCommerceCredentials(BaseModel):
    woocommerce_url: str
    consumer_key: str
    consumer_secret: str
    # προαιρετικό, το χρησιμοποιεί το UI σου
    sync_url: Optional[str] = None


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str


# ----------------- Users -----------------

class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    id: int
    is_active: bool
    credits: int
    woocommerce_url: Optional[str] = None
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    # για να μην “σκάει” όταν το επιστρέφεις
    sync_url: Optional[str] = None

    class Config:
        orm_mode = True


class UserUpdateWoocommerce(BaseModel):
    woocommerce_url: str
    consumer_key: str
    consumer_secret: str
    sync_url: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


# ----------------- Products / Posts -----------------

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    # Χαλαρώσεις για να μην κόβει validation & για συμβατότητα με DB
    price: Optional[Union[float, str]] = None
    image_url: Optional[Union[HttpUrl, str]] = None
    permalink: Optional[Union[HttpUrl, str]] = None
    categories: Optional[str] = None
    # προαιρετικά που μπορεί να υπάρχουν στο ORM σου
    sku: Optional[str] = None
    currency: Optional[str] = "EUR"
    stock: Optional[int] = None


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: int
    owner_id: int

    class Config:
        orm_mode = True


class PostBase(BaseModel):
    product_id: int
    type: str
    media_urls: List[str]
    caption: Optional[str]
    mode: Optional[str]


class PostCreate(PostBase):
    pass


class PostOut(PostBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class CreditResponse(BaseModel):
    message: str
    remaining_credits: int


# ----------------- Templates (DB-side) -----------------

class TemplateBase(BaseModel):
    name: str           # internal name
    type: str           # image | carousel | video
    file_path: str      # filesystem path


class TemplateCreate(TemplateBase):
    owner_id: Optional[int]


class TemplateOut(TemplateBase):
    id: int
    owner_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# ----------------- Template Engine (API requests) -----------------
# Τα παρακάτω βοηθούν να κρατάς το schema σε ένα σημείο
# και να μην “σπάει” με relative preview_url.

class TEnginePreviewRequest(BaseModel):
    """
    Preview αίτημα. Κρατάμε το schema χαλαρό γιατί το UI
    είτε στέλνει template_id/params είτε (ratio/mode/title/price…).
    """
    # Path A: άμεσο template render
    template_id: Optional[str] = None
    product_id: Optional[int] = None
    params: Optional[Dict[str, Any]] = None

    # Path B: wizard-friendly fields (όπως στέλνει το dashboard)
    post_type: Optional[str] = None
    mode: Optional[str] = None
    ratio: Optional[str] = None
    title: Optional[str] = None
    price: Optional[str] = None
    image_url: Optional[str] = None  # δέξου και μη-HttpUrl (π.χ. data URL)


class TEngineCommitRequest(BaseModel):
    """
    Commit αίτημα. Σημαντικό: preview_url = str (όχι HttpUrl)
    ώστε να επιτρέπονται και relative paths (/static/...).
    """
    template_id: Optional[str] = None
    product_id: Optional[int] = None
    preview_url: str
    caption: Optional[str] = None
    post_type: Optional[str] = None
