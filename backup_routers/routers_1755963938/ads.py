from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Product
from services.generator import generate_ad_content, generate_carousel_images, generate_video_ad
from routers.auth import get_current_user, User

router = APIRouter()

@router.post("/me/products/{product_id}/generate-ad")
def generate_ad(product_id: int, post_type: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id, Product.user_id == current_user.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if post_type == "image":
        url = generate_ad_content(product, post_type)
    elif post_type == "carousel":
        urls = generate_carousel_images(product)
        return {"urls": urls}
    elif post_type == "video":
        url = generate_video_ad(product)
    else:
        raise HTTPException(status_code=400, detail="Invalid post_type. Choose from 'image', 'carousel', 'video'.")

    return {"url": url}
