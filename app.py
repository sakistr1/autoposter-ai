from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import engine, get_db
from routers import auth, posts
from caption_generator import generate_caption
from image_generator import generate_post_image
from video_generator import generate_post_video

# Δημιουργία των πινάκων στη βάση
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS για frontend επικοινωνία
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount στατικοί φάκελοι
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/generated", StaticFiles(directory="generated"), name="generated")

# Templates (Jinja2)
templates = Jinja2Templates(directory="templates")

# ----------- Schemas -----------

class CaptionInput(BaseModel):
    name: str
    description: str
    price: str

class MediaInput(BaseModel):
    image_url: str
    caption: str

class CaptionOutput(BaseModel):
    caption: str

class MediaOutput(BaseModel):
    image_url: str | None = None
    video_url: str | None = None

# ----------- Routes -----------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login.html", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register.html", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Εισαγωγή routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(posts.router, prefix="/posts", tags=["posts"])

# Caption Generator
@app.post("/generate_caption", response_model=CaptionOutput)
def get_caption(input: CaptionInput, current_user: models.User = Depends(auth.get_current_user)):
    caption = generate_caption(input.name, input.description, input.price)
    return {"caption": caption}

# Image Generator
@app.post("/generate_image", response_model=MediaOutput)
def get_image(input: MediaInput, current_user: models.User = Depends(auth.get_current_user)):
    path = generate_post_image(input.image_url, input.caption)
    return {"image_url": f"/generated/{path}"}

# Video Generator
@app.post("/generate_video", response_model=MediaOutput)
def get_video(input: MediaInput, current_user: models.User = Depends(auth.get_current_user)):
    path = generate_post_video(input.image_url, input.caption)
    return {"video_url": f"/generated/{path}"}
