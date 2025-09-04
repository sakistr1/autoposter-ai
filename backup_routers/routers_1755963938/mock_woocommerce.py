from fastapi import APIRouter
from typing import List

router = APIRouter()

@router.get("/wp-json/wc/v3/products", response_model=List[dict])
def mock_products():
    # Επιστρέφει λίστα με demo προϊόντα
    return [
        {
            "id": 1,
            "name": "Demo Product 1",
            "description": "Περιγραφή demo προϊόντος 1",
            "images": [{"src": "https://via.placeholder.com/150"}]
        },
        {
            "id": 2,
            "name": "Demo Product 2",
            "description": "Περιγραφή demo προϊόντος 2",
            "images": [{"src": "https://via.placeholder.com/150"}]
        },
    ]
