import os
from cryptography.fernet import Fernet

FERNET_KEY = os.environ.get('FERNET_KEY')
if not FERNET_KEY:
    raise Exception("FERNET_KEY not set in environment!")

fernet = Fernet(FERNET_KEY)

def encrypt(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
