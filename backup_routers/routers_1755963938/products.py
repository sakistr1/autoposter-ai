# routers/products.py
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models.product import Product
from models.user import User
from schemas import ProductCreate  # ProductOut δεν χρειάζεται πλέον
from token_module import get_current_user

router = APIRouter(prefix="/me/products", tags=["products"])


# ---------------- Helpers ----------------
def _opt_str(v: Optional[object]) -> Optional[str]:
    """Return value as str or None."""
    if v is None or v == "":
        return None
    return str(v)


def _opt_float(v: Optional[object]) -> Optional[float]:
    """Return value as float ή None (δέχεται '9.99' ή 9.99)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _as_item(p: Product) -> Dict[str, Any]:
    """Normalize ORM Product → UI-friendly dict (ασφαλές αν λείπουν στήλες)."""
    def get(obj, name, default=None):
        return getattr(obj, name, default)

    price_val = get(p, "price", None)
    try:
        price = float(price_val) if price_val is not None else None
    except Exception:
        price = None

    updated = get(p, "updated_at", None)
    if hasattr(updated, "timestamp"):
        updated_at = int(updated.timestamp())
    elif isinstance(updated, (int, float)):
        updated_at = int(updated)
    else:
        updated_at = int(time.time())

    return {
        "id": get(p, "id"),
        "sku": get(p, "sku", None),
        "name": get(p, "name", ""),
        "price": price if price is not None else 0.0,
        "currency": get(p, "currency", "EUR"),
        "image": get(p, "image_url", None),
        "stock": get(p, "stock", None),
        "updated_at": updated_at,
    }


# ---------------- Endpoints ----------------
@router.get("")
def list_products(
    q: str = Query("", description="Search by name/SKU/description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Λίστα προϊόντων με αναζήτηση & σελιδοποίηση
    (ΜΟΝΟ τα προϊόντα του συνδεδεμένου χρήστη).
    """
    # Φίλτρο ιδιοκτησίας
    query = db.query(Product).filter(Product.owner_id == current_user.id)

    # Αναζήτηση
    if q:
        ilike = f"%{q}%"
        conds = [Product.name.ilike(ilike)]
        if hasattr(Product, "sku"):
            conds.append(getattr(Product, "sku").ilike(ilike))  # type: ignore[attr-defined]
        if hasattr(Product, "description"):
            conds.append(getattr(Product, "description").ilike(ilike))  # type: ignore[attr-defined]
        query = query.filter(or_(*conds))

    total = query.count()

    # Τα πιο “φρέσκα” πρώτα (updated_at αν υπάρχει, αλλιώς id)
    order_col = getattr(Product, "updated_at", None) or getattr(Product, "id")
    try:
        query = query.order_by(order_col.desc())  # type: ignore[attr-defined]
    except Exception:
        query = query.order_by(order_col)         # fallback

    rows: List[Product] = (
        query.offset((page - 1) * page_size)
             .limit(page_size)
             .all()
    )
    items = [_as_item(p) for p in rows]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/sync")
def sync_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stub για χειροκίνητο sync (WooCommerce κ.λπ. μπαίνει εδώ).
    Προς το παρόν επιστρέφει μόνο μετρήσεις του ΤΡΕΧΟΝΤΑ χρήστη.
    """
    total_user = db.query(Product).filter(Product.owner_id == current_user.id).count()
    return {"ok": True, "added": 0, "total": total_user}


@router.post("")  # χωρίς response_model για να μην κόβει σε optional fields
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Δημιουργία προϊόντος. Κάνουμε cast σε απλές Python τιμές
    (όχι Pydantic types π.χ. HttpUrl) πριν το insert.
    Επιστρέφουμε normalized dict.
    """
    kwargs: Dict[str, Any] = dict(
        name=product.name,
        description=getattr(product, "description", None),
        image_url=_opt_str(getattr(product, "image_url", None)),
        available=True,
        owner_id=current_user.id,
    )

    # Προαιρετικά/εξαρτώμενα από το ORM
    if hasattr(Product, "permalink"):
        kwargs["permalink"] = _opt_str(getattr(product, "permalink", None))
    if hasattr(Product, "categories"):
        kwargs["categories"] = _opt_str(getattr(product, "categories", None))
    if hasattr(Product, "sku"):
        kwargs["sku"] = _opt_str(getattr(product, "sku", None))
    if hasattr(Product, "currency"):
        kwargs["currency"] = _opt_str(getattr(product, "currency", "EUR"))
    if hasattr(Product, "price"):
        kwargs["price"] = _opt_float(getattr(product, "price", None))
    if hasattr(Product, "stock"):
        kwargs["stock"] = getattr(product, "stock", None)

    try:
        new_product = Product(**kwargs)
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return _as_item(new_product)
