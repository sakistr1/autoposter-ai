# main.py
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import logging
import os

from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session, relationship
from passlib.context import CryptContext

from database import get_db
from token_module import create_access_token, get_current_user
from models.user import User

log = logging.getLogger("uvicorn")
BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "production_engine" / "static" / "uploads"

# βεβαιωνόμαστε ότι υπάρχει ο φάκελος uploads (αλλιώς το StaticFiles σκάει στο startup)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(PAGES_DIR / "uploads").mkdir(parents=True, exist_ok=True)  # no-op αν υπάρχει ήδη

app = FastAPI(title="Autoposter AI")

# -------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if os.getenv("CORS_ALLOW_ORIGINS") else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ΠΡΩΤΑ mount το πιο συγκεκριμένο prefix για να μην “σκεπάζεται”
# /static/uploads  -> production_engine/static/uploads   (εκεί γράφουν τα endpoints upload_*)
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Έπειτα το γενικό /static από τον φάκελο static/
app.mount("/static", StaticFiles(directory=str(PAGES_DIR)), name="static")

# ===== ΣΙΓΑΣΗ access logs για 404 από static & favicon =====
class _IgnoreStatic404(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if " 404 " in msg and "/static/generated/" in msg:
            return False
        if "favicon.ico" in msg:
            return False
        return True

if os.getenv("SILENCE_STATIC_404", "1").lower() in ("1", "true", "yes"):
    logging.getLogger("uvicorn.access").addFilter(_IgnoreStatic404())

# Μικρό favicon για να μην υπάρχει αίτημα σε ανύπαρκτο αρχείο
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='14' font-size='14'>A</text></svg>"
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/healthz")
def healthz():
    return {"ok": True}

# ---------- RELATIONSHIP HOTFIX ΠΡΙΝ ΑΠΟ Ο,ΤΙΔΗΠΟΤΕ ----------
try:
    import models  # models/__init__.py κάνει dynamic autoload όλων των models

    # Template να υπάρχει στο registry αν ζητηθεί με string
    try:
        from models.template import Template  # noqa: F401
    except Exception as e:
        log.warning("[models] Template import skipped -> %s", e)

    # User <-> Post
    try:
        from models.post import Post
        from models.user import User as _U1
        if not hasattr(_U1, "posts"):
            _U1.posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
        if not hasattr(Post, "user"):
            Post.user = relationship("User", back_populates="posts")
    except Exception as e:
        log.warning("[models] Post/User hotfix skipped -> %s", e)

    # User <-> CreditTransaction
    try:
        from models.credit_transaction import CreditTransaction
        from models.user import User as _U2
        if not hasattr(_U2, "credit_transactions"):
            _U2.credit_transactions = relationship(
                "CreditTransaction", back_populates="user", cascade="all, delete-orphan"
            )
        if not hasattr(CreditTransaction, "user"):
            CreditTransaction.user = relationship("User", back_populates="credit_transactions")
    except Exception as e:
        log.warning("[models] CreditTransaction/User hotfix skipped -> %s", e)

    # User <-> Product  (reverse attr μπορεί να λέγεται user ή owner)
    try:
        from models.product import Product
        from models.user import User as _U3
        reverse_attr = "user" if hasattr(Product, "user") else ("owner" if hasattr(Product, "owner") else None)
        if reverse_attr is None:
            if not hasattr(Product, "user"):
                Product.user = relationship("User", back_populates="products")
            reverse_attr = "user"
        if not hasattr(_U3, "products"):
            _U3.products = relationship("Product", back_populates=reverse_attr, cascade="all, delete-orphan")
        if not hasattr(Product, reverse_attr):
            setattr(Product, reverse_attr, relationship("User", back_populates="products"))
    except Exception as e:
        log.warning("[models] Product/User hotfix skipped -> %s", e)

except Exception as e:
    log.warning("[models] autoload/hotfix failed -> %s", e)
# ---------------------------------------------------------------

# ================== EMBEDDED AUTH ROUTER ==================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
auth_router = APIRouter(tags=["auth"])

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

def _unique_username(db: Session, base: str) -> str:
    base = (base or "user").strip() or "user"
    name, i = base, 1
    while db.query(User).filter(User.username == name).first():
        i += 1
        name = f"{base}{i}"
    return name

@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(b: RegisterIn, db: Session = Depends(get_db)):
    e = _norm(b.email)
    if db.query(User).filter(User.email == e).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    uname = _unique_username(db, (b.username or e.split("@")[0]))
    u = User(
        email=e,
        username=uname,
        hashed_password=_hash(b.password),
        is_active=True,
    )
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id, "email": u.email, "username": u.username, "is_active": u.is_active}

@auth_router.post("/login", response_model=TokenOut)
def login(b: LoginIn, db: Session = Depends(get_db)):
    e = _norm(b.email)
    u = db.query(User).filter(User.email == e).first()
    if not u or not _verify(b.password, u.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token({"sub": u.email}), "token_type": "bearer"}

from fastapi.security import OAuth2PasswordRequestForm
@auth_router.post("/token", response_model=TokenOut)
def login_form(f: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    e = _norm(f.username)
    u = db.query(User).filter(User.email == e).first()
    if not u or not _verify(f.password, u.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token({"sub": u.email}), "token_type": "bearer"}

app.include_router(auth_router)
log.info("[routers] embedded auth loaded")
# =========================================================

# ===== Routers από production_engine =====
try:
    from production_engine.routers.previews import router as previews_router
    app.include_router(previews_router)
    log.info("[routers] loaded: production_engine.routers.previews")
except Exception as e:
    log.error("[routers] FAILED production_engine.routers.previews -> %s", e)

# Προσπάθησε πρώτα τον σωστό φάκελο tengine, αλλιώς παλιό όνομα templates_engine
_loaded_tengine = False
try:
    from production_engine.routers.tengine import router as tengine_router
    app.include_router(tengine_router)
    log.info("[routers] loaded: production_engine.routers.tengine")
    _loaded_tengine = True
except Exception as e:
    log.warning("[routers] production_engine.routers.tengine not found -> %s", e)
    try:
        from production_engine.routers.templates_engine import router as templates_engine_router
        app.include_router(templates_engine_router)
        log.info("[routers] loaded: production_engine.routers.templates_engine (fallback)")
        _loaded_tengine = True
    except Exception as e2:
        log.error("[routers] FAILED both tengine/templates_engine -> %s", e2)

try:
    from production_engine.routers.assets import router as assets_router
    app.include_router(assets_router)
    log.info("[routers] loaded: production_engine.routers.assets")
except Exception as e:
    log.warning("[routers] production_engine.routers.assets not loaded -> %s", e)

# === ΠΡΟΣΘΗΚΗ: Templates API (create/list/get) ===
try:
    from production_engine.routers.templates_api import router as templates_api_router
    app.include_router(templates_api_router)
    log.info("[routers] loaded: production_engine.routers.templates_api")
except Exception as e:
    log.error("[routers] FAILED production_engine.routers.templates_api -> %s", e)
# ===========================================================

# ---------------- CREDITS ------------------
@app.get("/me/credits", tags=["users"], include_in_schema=False)
def me_credits(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"credits": int(getattr(user, "credits", 0) or 0)}

# Δέχεται ΚΑΙ GET ΚΑΙ POST. amount ως query param (default 1).
@app.api_route("/me/use-credit", methods=["GET", "POST"], tags=["users"], include_in_schema=False)
def use_credit(
    amount: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    credits = int(getattr(user, "credits", 0) or 0)
    if credits < amount:
        raise HTTPException(status_code=402, detail="No credits")
    user.credits = credits - amount
    db.add(user); db.commit(); db.refresh(user)
    return {"ok": True, "credits": int(user.credits)}

# Προσθήκη credits (dev/buy simulation)
@app.post("/me/add-credits", tags=["users"], include_in_schema=False)
def add_credits(
    amount: int = Query(5, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cur = int(getattr(user, "credits", 0) or 0)
    user.credits = cur + amount
    db.add(user); db.commit(); db.refresh(user)
    return {"ok": True, "credits": int(user.credits)}
# -----------------------------------------------------------

# ----- ΣΕΛΙΔΕΣ -----
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/auth.html", status_code=302)

NO_STORE = {"Cache-Control": "no-store"}

@app.get("/auth.html", response_class=HTMLResponse)
def auth_html():
    p = PAGES_DIR / "auth.html"
    if p.exists():
        html = p.read_text(encoding="utf-8")
        return Response(content=html, media_type="text/html", headers=NO_STORE)
    return Response("<h1>Auth</h1>", media_type="text/html", headers=NO_STORE)

@app.get("/dashboard.html", response_class=HTMLResponse)
def dashboard_html():
    p = PAGES_DIR / "dashboard.html"
    if p.exists():
        html = p.read_text(encoding="utf-8")
        return Response(content=html, media_type="text/html", headers=NO_STORE)
    return Response("<h1>Dashboard</h1>", media_type="text/html", headers=NO_STORE)
