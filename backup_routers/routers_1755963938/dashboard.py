from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

DASH_PATH = os.path.join(TEMPLATES_DIR, "dashboard.html")

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_html(request: Request):
    resp = templates.TemplateResponse("dashboard.html", {"request": request})
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@router.get("/dashboard.html", response_class=HTMLResponse)
def dashboard_html_file(request: Request):
    return dashboard_html(request)

# HEAD να μην 405-άρει
@router.head("/dashboard.html")
def dashboard_head():
    resp = HTMLResponse(content=b"")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp
