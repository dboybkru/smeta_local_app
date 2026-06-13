import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    # Fernet требует 32-байтный urlsafe-base64 ключ; выводим из SECRET_KEY стабильно.
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
