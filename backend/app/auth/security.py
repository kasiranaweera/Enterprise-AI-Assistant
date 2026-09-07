"""
JWT-based session auth.

Login exchanges username/password (checked against the hardcoded
DEMO_USERS directory) for a short-lived JWT that carries the role.
Every protected route decodes that token via `get_current_user`, so
role is always derived from a signed token — never trusted from a
request body — which is what stops a user from just claiming to be an
admin in the chat payload (a common "tool abuse" vector called out in
the spec).
"""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.auth.models import DEMO_USERS, Role, User
from backend.app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

# Pre-hash demo passwords once at import time.
_HASHED_USERS = {
    uname: {**info, "password_hash": pwd_context.hash(info["password"])}
    for uname, info in DEMO_USERS.items()
}


def authenticate(username: str, password: str) -> User | None:
    record = _HASHED_USERS.get(username)
    if not record or not pwd_context.verify(password, record["password_hash"]):
        return None
    return User(username=username, role=record["role"], department=record["department"])


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user.username,
        "role": user.role.value,
        "department": user.department,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return User(username=payload["sub"], role=Role(payload["role"]), department=payload.get("department", "general"))
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    return decode_token(credentials.credentials)
