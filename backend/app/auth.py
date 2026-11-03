"""Staff sign-in. Staff accounts are seeded in the database; there is no public signup."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException

from .config import settings
from .db import engine
from .repository import get_staff_by_email
from .schemas import LoginRequest

JWT_ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32
BCRYPT_ROUNDS = 12
INVALID_CREDENTIALS = "Invalid email or password."

_dummy_hash: bytes | None = None


def _get_dummy_hash() -> bytes:
    """A real bcrypt hash used when the email is unknown, so both paths take similar time."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return _dummy_hash


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed stored hash: treat as a failed check rather than an error.
        return False


def signing_secret_is_strong() -> bool:
    secret = settings.jwt_secret
    return secret != "change-me" and len(secret) >= MIN_SECRET_LENGTH


def create_access_token(staff_id: int, email: str) -> tuple[str, int]:
    """Return (token, lifetime in seconds). Raises RuntimeError if the signing secret is weak."""
    if not signing_secret_is_strong():
        raise RuntimeError("JWT_SECRET must be set to a random value of at least 32 characters.")

    now = datetime.now(timezone.utc)
    lifetime = timedelta(hours=settings.jwt_expiry_hours)
    payload = {
        "sub": str(staff_id),
        "email": email,
        "role": "staff",
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


REQUIRED_CLAIMS = ["sub", "email", "role", "iat", "exp"]


def require_staff(authorization: str | None = Header(default=None)) -> dict:
    """Dependency for staff-only routes.

    401 when the token is missing, malformed, badly signed, expired, or has the wrong algorithm.
    403 when the token is valid but its role is not 'staff'.
    """
    if not signing_secret_is_strong():
        raise HTTPException(status_code=503, detail="Sign-in is not configured.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in is required.")

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in is required.")

    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],  # pinned: rejects "alg": "none" and other algorithms
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Your session is not valid. Please sign in again.")

    if claims.get("role") != "staff":
        raise HTTPException(status_code=403, detail="Staff access only.")

    return claims


router = APIRouter()


@router.post("/auth/login")
def login(body: LoginRequest) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    if not signing_secret_is_strong():
        raise HTTPException(status_code=503, detail="Sign-in is not configured.")

    with engine.begin() as conn:
        staff = get_staff_by_email(conn, body.email)

    # Always run one bcrypt check, even for an unknown email, so timing does not reveal which emails exist.
    stored_hash = staff.password_hash.encode("utf-8") if staff is not None else _get_dummy_hash()
    password_ok = verify_password(body.password, stored_hash.decode("utf-8"))

    if staff is None or not password_ok:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)

    token, expires_in = create_access_token(staff.id, staff.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "role": "staff",
    }


@router.get("/auth/me")
def me(claims: dict = Depends(require_staff)) -> dict:
    return {
        "staff_id": int(claims["sub"]),
        "email": claims["email"],
        "role": claims["role"],
    }
