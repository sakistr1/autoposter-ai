from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
import os, uuid, shutil

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_ROOT = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

ALLOWED_IMG = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

def _save_upload(dst_dir: str, file: UploadFile) -> str:
    os.makedirs(dst_dir, exist_ok=True)
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMG:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    safe_name = f"{uuid.uuid4()}{ext}"
    dst_path = os.path.join(dst_dir, safe_name)
    with open(dst_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    rel = os.path.relpath(dst_path, STATIC_DIR)
    return f"/static/{rel.replace(os.sep, '/')}"

@router.post("/upload_logo")  # <<-- ΣΧΕΤΙΚΟ μονοπάτι
async def upload_logo(file: UploadFile = File(...)):
    dst_dir = os.path.join(UPLOAD_ROOT, "brand")
    url = _save_upload(dst_dir, file)
    return {"url": url}

@router.post("/upload_product_images")  # <<-- ΣΧΕΤΙΚΟ μονοπάτι
async def upload_product_images(
    files: List[UploadFile] = File(...),
    product_id: int = Form(...)
):
    urls: List[str] = []
    dst_dir = os.path.join(UPLOAD_ROOT, "products", str(product_id))
    for f in files:
        urls.append(_save_upload(dst_dir, f))
    return {"urls": urls}
