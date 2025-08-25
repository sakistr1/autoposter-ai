# backend/services/canva.py

import httpx
import urllib.parse
import os
from dotenv import load_dotenv

load_dotenv()

CANVA_CLIENT_ID = os.getenv("CANVA_CLIENT_ID")
CANVA_CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET")
CANVA_REDIRECT_URI = os.getenv("CANVA_REDIRECT_URI", "http://localhost:8000/canva/callback")
CANVA_AUTH_BASE = "https://www.canva.com/oauth/authorize"
CANVA_TOKEN_URL = "https://api.canva.com/auth/token"

def get_canva_authorization_url():
    params = {
        "client_id": CANVA_CLIENT_ID,
        "redirect_uri": CANVA_REDIRECT_URI,
        "response_type": "code",
        "scope": "designs.read designs.write",
    }
    url = f"{CANVA_AUTH_BASE}?{urllib.parse.urlencode(params)}"
    return url

async def exchange_code_for_token(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            CANVA_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CANVA_REDIRECT_URI,
                "client_id": CANVA_CLIENT_ID,
                "client_secret": CANVA_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        return response.json()
