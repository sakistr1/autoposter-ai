from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from token_module import create_access_token
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

from models.user import User  # direct import, όχι από models.__init__

router = APIRouter(tags=["auth"])

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

def _norm(e: str) -> str: return e.strip().lower()
def _hash(p: str) -> str: return pwd_context.hash(p)
def _verify(p: str, h: str) -> bool: return pwd_context.verify(p, h)

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = _norm(payload.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=email,
        username=(payload.username or email.split("@")[0]),
        hashed_password=_hash(payload.password),
        is_active=True,
    )
    db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "email": user.email, "username": user.username, "is_active": user.is_active}

@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = _norm(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}

from fastapi.security import OAuth2PasswordRequestForm
@router.post("/token", response_model=TokenOut)
def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = _norm(form_data.username)
    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}
