import os
from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

JWT_SECRET = os.environ.get('GLIMMER_JWT_SECRET') or 'CHANGE_ME_IN_PROD'
JWT_ALG = 'HS256'
JWT_EXPIRE_MINUTES = int(os.environ.get('GLIMMER_JWT_EXPIRE_MINUTES') or 60 * 24 * 7)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = datetime.utcnow()
    exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        'sub': subject,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
