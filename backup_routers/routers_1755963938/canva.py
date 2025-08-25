from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from services import canva
from routers.auth import get_current_user
from models.user import User  # ΔΙΟΡΘΩΜΕΝΟ import

router = APIRouter(prefix="/canva")

@router.get("/login")
def login():
    return RedirectResponse(url=canva.get_canva_authorization_url())

@router.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "Missing code parameter"}
    
    token = await canva.exchange_code_for_token(code)
    return {"access_token": token}

@router.get("/connect")
def connect(current_user: User = Depends(get_current_user)):
    return {"message": f"User {current_user.email} connected to Canva."}
