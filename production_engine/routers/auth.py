from pydantic import BaseModel

class UserInfo(BaseModel):
    email: str = "demo@example.com"

# FastAPI dependency-friendly υπογραφή (προαιρετικά Authorization header)
def get_current_user(authorization: str | None = None) -> UserInfo:
    # Αν θες, μπορείς εδώ να κάνεις parsing στο token.
    return UserInfo(email="demo@example.com")
