# production_engine/routers/shortlinks.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from token_module import get_current_user
from pathlib import Path
import sqlite3, time

router = APIRouter(prefix="/shortlinks", tags=["shortlinks"])

DB_PATH = Path("static/logs/database.db")

class ShortlinkCreate(BaseModel):
    url: str

def _get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS shortlinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            url TEXT,
            created_at INTEGER
        )"""
    )
    return con

@router.post("/")  # canonical (με slash)
def create_shortlink(req: ShortlinkCreate, user=Depends(get_current_user)):
    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(422, "invalid target url")
    code = hex(int(time.time() * 1000))[2:]
    con = _get_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO shortlinks (code,url,created_at) VALUES (?,?,?)",
        (code, req.url, int(time.time())),
    )
    con.commit()
    return {"ok": True, "code": code, "short_url": f"/go/{code}", "target_url": req.url}

# optional: δέχεται και /shortlinks (χωρίς slash) για να μην κάνει 307
@router.post("")
def create_shortlink_no_slash(req: ShortlinkCreate, user=Depends(get_current_user)):
    return create_shortlink(req, user)

@router.get("/{code}")
def get_shortlink(code: str, user=Depends(get_current_user)):
    con = _get_db()
    cur = con.cursor()
    row = cur.execute("SELECT url,created_at FROM shortlinks WHERE code=?", (code,)).fetchone()
    if not row:
        raise HTTPException(404, "shortlink not found")
    return {"ok": True, "code": code, "url": row[0], "created_at": row[1]}
