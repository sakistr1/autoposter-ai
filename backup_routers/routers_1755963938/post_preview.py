from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Post
import os

router = APIRouter()

# ✅ Templates directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ✅ GET /post/{post_id}
@router.get("/post/{post_id}")
def post_preview(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    caption = f"📢 {post.type.upper()} Post για το προϊόν σας!\n👉 Δες περισσότερα: [βάλε link εδώ]"
    return templates.TemplateResponse("post_preview.html", {
        "request": request,
        "post": post,
        "caption": caption
    })
