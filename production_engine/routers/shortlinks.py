from __future__ import annotations

import time
import sqlite3
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

# Auth
from token_module import get_current_user

router = APIRouter(tags=["shortlinks"])

DB_PATH = Path("static/logs/database.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS shortlinks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        url TEXT NOT NULL,
        created_at INTEGER NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS shortlink_clicks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        ts INTEGER NOT NULL,
        ip TEXT,
        ua TEXT
    )""")
    return con

def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return u
    # basic sanity
    if u.startswith("/go/"):
        return u
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u

def _mk_code(n: int = 10) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(n))

class ShortlinkCreate(BaseModel):
    url: str

@router.post("/shortlinks")
def create_shortlink(body: ShortlinkCreate, user = Depends(get_current_user)):
    url = _normalize_url(body.url)
    if not url:
        raise HTTPException(400, "url is required")

    con = _db()
    cur = con.cursor()
    # idempotent per URL
    row = cur.execute("SELECT code FROM shortlinks WHERE url=? LIMIT 1", (url,)).fetchone()
    if row:
        code = row[0]
    else:
        code = _mk_code()
        cur.execute("INSERT INTO shortlinks(code,url,created_at) VALUES(?,?,?)", (code, url, int(time.time())))
        con.commit()
    con.close()
    return {"code": code, "url": url, "created_at": int(time.time())}

@router.get("/go/{code}")
def go_redirect(code: str, request: Request):
    con = _db()
    row = con.execute("SELECT url FROM shortlinks WHERE code=? LIMIT 1", (code,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Short code not found")
    url = row[0]

    # clicks logging (best-effort)
    try:
        ip = request.headers.get("x-forwarded-for") or request.client.host
        ua = request.headers.get("user-agent")
        con.execute("INSERT INTO shortlink_clicks(code,ts,ip,ua) VALUES(?,?,?,?)",
                    (code, int(time.time()), ip, ua))
        con.commit()
    except Exception:
        pass
    finally:
        con.close()

    return RedirectResponse(url=url, status_code=302)

@router.get("/shortlinks/stats/{code}")
def shortlink_stats(code: str, user = Depends(get_current_user)):
    con = _db()
    total = con.execute("SELECT COUNT(*) FROM shortlink_clicks WHERE code=?", (code,)).fetchone()[0]
    last24 = con.execute("SELECT COUNT(*) FROM shortlink_clicks WHERE code=? AND ts>=?",
                         (code, int(time.time()) - 24*3600)).fetchone()[0]
    last7d = con.execute("SELECT COUNT(*) FROM shortlink_clicks WHERE code=? AND ts>=?",
                         (code, int(time.time()) - 7*24*3600)).fetchone()[0]
    con.close()
    return {"code": code, "total": total, "last24h": last24, "last7d": last7d}
