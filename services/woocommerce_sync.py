# services/woocommerce_sync.py
from __future__ import annotations

import time
from typing import Any, Dict, Optional, List

import requests
from requests.auth import HTTPBasicAuth
from sqlalchemy.orm import Session

# Προσαρμοσμένο στα imports που χρησιμοποιούμε και αλλού
from models.product import Product
from models.user import User


class WooError(RuntimeError):
    ...


class WooClient:
    def __init__(self, base_url: str, key: str, secret: str, timeout: int = 15):
        if not base_url:
            raise WooError("Missing Woo base URL")
        self.base = base_url.rstrip("/")
        self.key = (key or "").strip()
        self.secret = (secret or "").strip()
        if not self.key or not self.secret:
            raise WooError("Missing Woo credentials (key/secret)")
        self.timeout = timeout

    def _get(self, path: str, params: Dict[str, Any]) -> (Any, Dict[str, str]):
        url = f"{self.base}/wp-json/wc/v3{path}"
        r = requests.get(url, auth=HTTPBasicAuth(self.key, self.secret),
                         params=params, timeout=self.timeout)
        if not r.ok:
            raise WooError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
        return r.json(), r.headers

    def iter_products(self, per_page: int = 50):
        page = 1
        while True:
            data, headers = self._get("/products", {"page": page, "per_page": per_page})
            if not data:
                break
            for p in data:
                yield p
            total_pages = int(headers.get("X-WP-TotalPages", "1"))
            if page >= total_pages:
                break
            page += 1


def _first_image_url(p: Dict[str, Any]) -> Optional[str]:
    imgs = p.get("images") or []
    return imgs[0].get("src") if imgs else None


def _category_string(p: Dict[str, Any]) -> Optional[str]:
    cats = p.get("categories") or []
    names = [c.get("name") for c in cats if c.get("name")]
    return ", ".join(names) if names else None


def _price(p: Dict[str, Any]) -> Optional[float]:
    # Woo δίνει strings
    for k in ("sale_price", "regular_price", "price"):
        v = p.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except Exception:
                continue
    return None


def upsert_from_woo(db: Session, user: User, woo: WooClient) -> Dict[str, int]:
    """
    Τραβάει προϊόντα από Woo και κάνει upsert σε Product.
    Κριτήρια: προτιμά sku, μετά permalink, αλλιώς fallback.
    ΔΕΝ διαγράφει όλα — ενημερώνει/προσθέτει.
    """
    added = 0
    updated = 0
    now_ts = int(time.time())

    for wp in woo.iter_products():
        sku = (wp.get("sku") or None) if hasattr(Product, "sku") else None
        permalink = (wp.get("permalink") or None) if hasattr(Product, "permalink") else None

        # Βρες υπάρχον
        obj = None
        q = db.query(Product)
        if sku:
            obj = q.filter(getattr(Product, "sku") == sku).first()
        elif permalink:
            obj = q.filter(getattr(Product, "permalink") == permalink).first()

        fields: Dict[str, Any] = dict(
            name=wp.get("name") or "",
            description=wp.get("short_description") or wp.get("description") or None,
            image_url=_first_image_url(wp),
            available=(wp.get("status") == "publish"),
            owner_id=user.id,
        )
        if hasattr(Product, "permalink"):
            fields["permalink"] = permalink
        if hasattr(Product, "categories"):
            fields["categories"] = _category_string(wp)
        if hasattr(Product, "sku"):
            fields["sku"] = sku
        if hasattr(Product, "currency"):
            fields["currency"] = "EUR"
        if hasattr(Product, "price"):
            fields["price"] = _price(wp)
        if hasattr(Product, "stock"):
            stock_q = wp.get("stock_quantity")
            fields["stock"] = int(stock_q) if isinstance(stock_q, (int, float)) else None
        if hasattr(Product, "updated_at"):
            fields["updated_at"] = now_ts

        if obj is None:
            obj = Product(**fields)
            db.add(obj)
            added += 1
        else:
            for k, v in fields.items():
                setattr(obj, k, v)
            updated += 1

    db.commit()
    return {"added": added, "updated": updated, "total": db.query(Product).count()}


# ---- Backwards compatible wrapper (παλιό όνομα) ----
def fetch_and_store_products_from_woocommerce(db: Session, user: User):
    """
    Συμβατότητα με το παλιό API σας: απλός wrapper που
    χρησιμοποιεί το νέο client/upsert και επιστρέφει stats.
    """
    woo = WooClient(
        base_url=getattr(user, "woocommerce_url", "") or "",
        key=getattr(user, "consumer_key", "") or "",
        secret=getattr(user, "consumer_secret", "") or "",
    )
    return upsert_from_woo(db, user, woo)
