import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import phonenumbers
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession
from .config import get_settings
from .db import get_db
from .models import Session, User

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
COOKIE = "threeds_session"


def normalize_phone(value: str) -> str:
    try:
        parsed = phonenumbers.parse(value, "IN")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception as exc:
        raise HTTPException(422, detail={"code": "invalid_phone", "message": "Enter a valid Indian mobile number."}) from exc


def hash_password(value: str) -> str:
    return ph.hash(value)


def verify_password(hashed: str, value: str) -> bool:
    try:
        return ph.verify(hashed, value)
    except VerifyMismatchError:
        return False


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(db: DBSession, user: User, response: Response) -> Session:
    cfg = get_settings()
    raw = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    if user.role == "ADMIN":
        rolling = timedelta(hours=cfg.admin_session_hours)
        absolute = rolling
    else:
        rolling = timedelta(days=cfg.session_days)
        absolute = timedelta(days=90)
    row = Session(user_id=user.id, token_hash=token_hash(raw), csrf_token=secrets.token_urlsafe(32), expires_at=now + rolling, absolute_expires_at=now + absolute)
    db.add(row)
    db.commit()
    response.set_cookie(COOKIE, raw, max_age=int(rolling.total_seconds()), httponly=True, secure=cfg.cookie_secure, samesite="lax", path="/")
    return row


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def current_session(response: Response, threeds_session: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> Session:
    if not threeds_session:
        raise HTTPException(401, detail={"code": "not_authenticated", "message": "Sign in to continue."})
    row = db.query(Session).filter(Session.token_hash == token_hash(threeds_session), Session.revoked_at.is_(None)).first()
    now = datetime.now(timezone.utc)
    if not row or _aware(row.expires_at) <= now or _aware(row.absolute_expires_at) <= now or not row.user.active:
        raise HTTPException(401, detail={"code": "session_expired", "message": "Your session has expired."})
    cfg = get_settings()
    if row.user.role != "ADMIN" and _aware(row.expires_at) - now < timedelta(days=max(1, cfg.session_days // 2)):
        renewed = min(now + timedelta(days=cfg.session_days), _aware(row.absolute_expires_at))
        row.expires_at = renewed
        response.set_cookie(COOKIE, threeds_session, max_age=max(0, int((renewed - now).total_seconds())), httponly=True, secure=cfg.cookie_secure, samesite="lax", path="/")
    row.last_seen_at = now
    db.commit()
    return row


def current_user(session: Session = Depends(current_session)) -> User:
    return session.user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, detail={"code": "admin_required", "message": "Administrator access required."})
    return user


def verify_csrf(request: Request, session: Session = Depends(current_session), csrf: str | None = Header(default=None, alias="X-CSRF-Token")) -> Session:
    cfg = get_settings()
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in cfg.origins and origin.rstrip("/") != cfg.base_url.rstrip("/"):
        raise HTTPException(403, detail={"code": "bad_origin", "message": "Request origin is not allowed."})
    if not csrf or not secrets.compare_digest(csrf, session.csrf_token):
        raise HTTPException(403, detail={"code": "csrf_failed", "message": "Security token is missing or expired."})
    return session

