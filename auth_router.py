# auth_router.py — root module για /register, /login, /token
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from token_module import create_access_token
from passlib.context import CryptContext
from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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

def _n(e): return e.strip().lower()
def _h(p): return pwd_context.hash(p)
def _v(p,h): return pwd_context.verify(p,h)

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(b: RegisterIn, db: Session = Depends(get_db)):
    e=_n(b.email)
    if db.query(User).filter(User.email==e).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    u=User(email=e, username=(b.username or e.split("@")[0]), hashed_password=_h(b.password), is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return {"id":u.id,"email":u.email,"username":u.username,"is_active":u.is_active}

@router.post("/login", response_model=TokenOut)
def login(b: LoginIn, db: Session = Depends(get_db)):
    e=_n(b.email); u=db.query(User).filter(User.email==e).first()
    if not u or not _v(b.password, u.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token({"sub": u.email}), "token_type":"bearer"}

from fastapi.security import OAuth2PasswordRequestForm
@router.post("/token", response_model=TokenOut)
def login_form(f: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    e=_n(f.username); u=db.query(User).filter(User.email==e).first()
    if not u or not _v(f.password, u.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token({"sub": u.email}), "token_type":"bearer"}
