from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.product import Product
from models.user import User
from schemas import ProductOut
from database import get_db
from token_module import get_current_user
import requests

router = APIRouter()

@router.post("/me/products/sync", response_model=list[ProductOut])
def sync_products_from_url(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print("DEBUG current_user type:", type(current_user))
    print("DEBUG current_user fields:", vars(current_user))

    if not hasattr(current_user, 'sync_url'):
        raise HTTPException(status_code=400, detail="Το sync_url δεν υπάρχει στο αντικείμενο current_user.")

    if not current_user.sync_url:
        raise HTTPException(status_code=400, detail="Το sync_url δεν έχει οριστεί για τον χρήστη.")

    try:
        response = requests.get(current_user.sync_url, timeout=10)
        response.raise_for_status()
        external_products = response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Αποτυχία σύνδεσης στο eShop: {str(e)}")

    synced = []
    for p in external_products:
        name = p.get("name")
        description = p.get("description", "")
        image_url = p.get("image", "")

        if not name:
            continue  # αγνοούμε προϊόν χωρίς όνομα

        existing = db.query(Product).filter(
            Product.name == name,
            Product.owner_id == current_user.id
        ).first()

        if existing:
            existing.description = description
            existing.image_url = image_url
            db.commit()
            db.refresh(existing)
            synced.append(existing)
        else:
            new_product = Product(
                name=name,
                description=description,
                image_url=image_url,
                available=True,
                owner_id=current_user.id
            )
            db.add(new_product)
            db.commit()
            db.refresh(new_product)
            synced.append(new_product)

    return synced
