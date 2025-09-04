# routers/users.py
from fastapi import APIRouter, Depends, Body, Form, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(tags=["auth"])

# ---- helpers: προσαρμόσ’ τα στον δικό σου κώδικα --------------------------
def _get_user_by_username_or_email(username: Optional[str], email: Optional[str]):
    """
    Επιστρέφει user ή None από τη ΒΔ.
    Υλοποίησέ τη με το ORM σου: by username πρώτα, αλλιώς by email.
    """
    ...

def _verify_password(plain: str, hashed: str) -> bool:
    """
    Έλεγχος κωδικού (π.χ. passlib). Προσαρμογή στη δική σου υλοποίηση.
    """
    ...

def _create_access_token(sub: str) -> str:
    """
    Γεννά JWT και γυρνά το string (ώριμο, αυτό που ήδη χρησιμοποιείς).
    """
    ...
# ---------------------------------------------------------------------------

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterIn(BaseModel):
    email: EmailStr
    username: str
    password: str

class LoginJSON(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn):
    # έλεγχος ύπαρξης
    existing = _get_user_by_username_or_email(data.username, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    # δημιούργησε χρήστη + hash
    # save_user(email=data.email, username=data.username, hashed=hash_password(data.password))
    # πάρε ξανά τον χρήστη για το sub
    user = _get_user_by_username_or_email(data.username, data.email)
    token = _create_access_token(sub=user.email)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login", response_model=TokenOut)
def login_json(data: LoginJSON = Body(...)):
    user = _get_user_by_username_or_email(data.username, data.email)
    if not user or not _verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_access_token(sub=user.email)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/users/login", response_model=TokenOut)
def login_form(username: str = Form(...), password: str = Form(...)):
    user = _get_user_by_username_or_email(username, None)
    if not user or not _verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_access_token(sub=user.email)
    return {"access_token": token, "token_type": "bearer"}
