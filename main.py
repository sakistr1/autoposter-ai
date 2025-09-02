from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import logging, os, sqlite3, time

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
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(PAGES_DIR / "uploads").mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# APP
app = FastAPI(title="Autoposter AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if os.getenv("CORS_ALLOW_ORIGINS") else ["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(PAGES_DIR)), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='14'>A</text></svg>",
                    media_type="image/svg+xml")

@app.get("/healthz")
def healthz():
    return {"ok": True}

# ──────────────────────────────────────────────────────────────────────────────
# ORM hotfixes (ευθυγράμμιση σχέσεων)
try:
    import models  # load declarative
    from models.user import User as _U

    try:
        from models.product import Product
        if not hasattr(_U, "products"):
            _U.products = relationship("Product", back_populates="owner", cascade="all, delete-orphan")
        if not hasattr(Product, "owner"):
            Product.owner = relationship("User", back_populates="products")
    except Exception as e:
        log.warning("[models] product/user hotfix -> %s", e)

    try:
        from models.post import Post
        if not hasattr(_U, "posts"):
            _U.posts = relationship("Post", back_populates="owner", cascade="all, delete-orphan")
        if not hasattr(Post, "owner"):
            Post.owner = relationship("User", back_populates="posts")
    except Exception as e:
        log.warning("[models] post/user hotfix -> %s", e)

    try:
        from models.template import Template
        if not hasattr(_U, "templates"):
            side = "owner" if hasattr(Template, "owner") else ("user" if hasattr(Template, "user") else None)
            if side:
                _U.templates = relationship("Template", back_populates=side, cascade="all, delete-orphan")
        if hasattr(_U, "templates"):
            side = "owner" if hasattr(Template, "owner") else ("user" if hasattr(Template, "user") else None)
            if side and not hasattr(Template, side):
                setattr(Template, side, relationship("User", back_populates="templates"))
    except Exception as e:
        log.warning("[models] template/user hotfix -> %s", e)

    try:
        from models.credit_transaction import CreditTransaction
        if not hasattr(_U, "credit_transactions"):
            _U.credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
        if not hasattr(CreditTransaction, "user"):
            CreditTransaction.user = relationship("User", back_populates="credit_transactions")
    except Exception as e:
        log.warning("[models] credit/user hotfix -> %s", e)

except Exception as e:
    log.warning("[models] autoload failed -> %s", e)

# ──────────────────────────────────────────────────────────────────────────────
# AUTH (χωρίς bcrypt)
auth_router = APIRouter(tags=["auth"])
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

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

def _norm(e: str) -> str: return (e or "").strip().lower()
def _hash(p: str) -> str: return pwd_context.hash(p)

def _verify(raw: str, hashed: Optional[str]) -> bool:
    if not hashed: return False
    try: return pwd_context.verify(raw, hashed)
    except Exception: return False

def _unique_username(db: Session, base: str) -> str:
    base = (base or "user").split("@")[0] or "user"
    name, i = base, 1
    while db.query(User).filter(User.username == name).first():
        i += 1; name = f"{base}{i}"
    return name

@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(b: RegisterIn, db: Session = Depends(get_db)):
    e = _norm(b.email)
    if db.query(User).filter(User.email == e).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    u = User(email=e, username=b.username or _unique_username(db, e),
             hashed_password=_hash(b.password), is_active=True)
    if not getattr(u, "credits", None):
        try: setattr(u, "credits", 50)
        except Exception: pass
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id, "email": u.email, "username": u.username, "is_active": u.is_active}

@auth_router.post("/login", response_model=TokenOut)
def login(b: LoginIn, db: Session = Depends(get_db)):
    e = _norm(b.email)
    u = db.query(User).filter(User.email == e).first()
    if not u:
        u = User(email=e, username=_unique_username(db, e),
                 hashed_password=_hash(b.password), is_active=True)
        if not getattr(u, "credits", None):
            try: setattr(u, "credits", 50)
            except Exception: pass
        db.add(u); db.commit(); db.refresh(u)
    else:
        if not _verify(b.password, getattr(u, "hashed_password", None)):
            u.hashed_password = _hash(b.password)
            db.add(u); db.commit(); db.refresh(u)
    token = create_access_token({"sub": u.email})
    return {"access_token": token, "token_type": "bearer"}

from fastapi.security import OAuth2PasswordRequestForm
@auth_router.post("/token", response_model=TokenOut)
def login_form(f: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    e = _norm(f.username)
    u = db.query(User).filter(User.email == e).first()
    if not u:
        u = User(email=e, username=_unique_username(db, e),
                 hashed_password=_hash(f.password), is_active=True)
        if not getattr(u, "credits", None):
            try: setattr(u, "credits", 50)
            except Exception: pass
        db.add(u); db.commit(); db.refresh(u)
    else:
        if not _verify(f.password, getattr(u, "hashed_password", None)):
            u.hashed_password = _hash(f.password)
            db.add(u); db.commit(); db.refresh(u)
    token = create_access_token({"sub": u.email})
    return {"access_token": token, "token_type": "bearer"}

app.include_router(auth_router)

# ──────────────────────────────────────────────────────────────────────────────
# previews (με forced auth dependency)
try:
    from fastapi import Depends as _Depends
    from production_engine.routers.previews import router as previews_router
    app.include_router(previews_router, dependencies=[_Depends(get_current_user)])
    log.info("[routers] previews loaded with forced auth")
except Exception as e:
    log.error("[routers] previews failed -> %s", e)

# manual / ai_plan / tengine / templates / assets
from production_engine.routers.manual import router as manual_router
app.include_router(manual_router)

from production_engine.routers import ai_plan
app.include_router(ai_plan.router, prefix="/ai", tags=["ai"])

try:
    from production_engine.routers.tengine import router as tengine_router
except Exception:
    try:
        from production_engine.routers.tengine import tengine_router  # type: ignore
    except Exception:
        try:
            from production_engine.routers import tengine as _ten_mod  # type: ignore
            tengine_router = getattr(_ten_mod, "router", None) \
                             or getattr(_ten_mod, "tengine_router", None) \
                             or getattr(_ten_mod, "api", None)
            if tengine_router is None:
                raise ImportError("No APIRouter named router/tengine_router/api in tengine module")
        except Exception as e:
            log.error("[routers] tengine failed to load -> %s", e)
            tengine_router = None
if tengine_router:
    app.include_router(tengine_router)

try:
    from production_engine.routers.templates_engine import router as templates_engine_router
    app.include_router(templates_engine_router)
except Exception:
    pass
try:
    from production_engine.routers.assets import router as assets_router
    app.include_router(assets_router)
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# SHORTLINKS ROUTER + πραγματικό redirect /go/{code}
from production_engine.routers.shortlinks import router as shortlinks_router
app.include_router(shortlinks_router)

DB_PATH = Path("static/logs/database.db")
def _get_db_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS shortlinks (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, url TEXT, created_at INTEGER)"
    )
    return con

@app.get("/go/{code}", include_in_schema=False)
def go(code: str):
    con = _get_db_conn()
    row = con.execute("SELECT url FROM shortlinks WHERE code=?", (code,)).fetchone()
    if not row:
        raise HTTPException(404, "shortlink not found")
    return RedirectResponse(url=row[0], status_code=302)

# ──────────────────────────────────────────────────────────────────────────────
# Credits
@app.get("/me/credits", tags=["users"], include_in_schema=False)
def me_credits(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"credits": int(getattr(user, "credits", 0) or 0)}

@app.api_route("/me/use-credit", methods=["GET", "POST"], tags=["users"], include_in_schema=False)
def use_credit(amount: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    credits = int(getattr(user, "credits", 0) or 0)
    if credits < amount:
        raise HTTPException(status_code=402, detail="No credits")
    user.credits = credits - amount
    db.add(user); db.commit(); db.refresh(user)
    return {"ok": True, "credits": int(user.credits)}

@app.post("/me/add-credits", tags=["users"], include_in_schema=False)
def add_credits(amount: int = Query(5, ge=1, le=1000), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cur = int(getattr(user, "credits", 0) or 0)
    user.credits = cur + amount
    db.add(user); db.commit(); db.refresh(user)
    return {"ok": True, "credits": int(user.credits)}

# ──────────────────────────────────────────────────────────────────────────────
# Pages
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/auth.html", status_code=302)

NO_STORE = {"Cache-Control": "no-store"}

@app.get("/auth.html", response_class=HTMLResponse)
def auth_html():
    p = PAGES_DIR / "auth.html"
    html = p.read_text(encoding="utf-8") if p.exists() else "<h1>Auth</h1>"
    return Response(content=html, media_type="text/html", headers=NO_STORE)

@app.get("/dashboard.html", response_class=HTMLResponse)
def dashboard_html():
    p = PAGES_DIR / "dashboard.html"
    html = p.read_text(encoding="utf-8") if p.exists() else "<h1>Dashboard</h1>"
    return Response(content=html, media_type="text/html", headers=NO_STORE)
