from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Session as AuthSession, User
from ..schemas import LoginIn, RegisterIn
from ..security import COOKIE, create_session, current_session, hash_password, normalize_phone, token_hash, verify_csrf, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
attempts: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str, limit=8, window=300):
    now = datetime.now(timezone.utc).timestamp()
    bucket = attempts[key]
    while bucket and bucket[0] < now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(429, detail={"code": "rate_limited", "message": "Too many attempts. Please wait and try again."})
    bucket.append(now)


def auth_json(row: AuthSession):
    u = row.user
    return {"user": {"id": u.id, "full_name": u.full_name, "phone": u.phone, "email": u.email, "role": u.role,
                     "phone_verified": False}, "csrf_token": row.csrf_token}


@router.post("/register", status_code=201)
def register(data: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit("reg:" + (request.client.host if request.client else "unknown"), 6, 900)
    phone = normalize_phone(data.phone)
    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(409, detail={"code": "phone_in_use", "message": "An account already uses this mobile number."})
    user = User(full_name=data.full_name.strip(), phone=phone, email=str(data.email) if data.email else None, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return auth_json(create_session(db, user, response))


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    rate_limit("login:" + ip, 12, 300)
    phone = normalize_phone(data.phone)
    user = db.query(User).filter(User.phone == phone).first()
    now = datetime.now(timezone.utc)
    if user and user.locked_until and (user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)) > now:
        raise HTTPException(429, detail={"code": "temporarily_locked", "message": "Too many attempts. Please try again later."})
    if not user or not user.active or not verify_password(user.password_hash, data.password):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 7:
                user.locked_until = now + timedelta(minutes=10)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Mobile number or password is incorrect."})
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    return auth_json(create_session(db, user, response))


@router.get("/me")
def me(row: AuthSession = Depends(current_session)):
    return auth_json(row)


@router.get("/status")
def status(threeds_session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not threeds_session:
        return {"authenticated": False}
    row = db.query(AuthSession).filter(AuthSession.token_hash == token_hash(threeds_session), AuthSession.revoked_at.is_(None)).first()
    now = datetime.now(timezone.utc)
    if not row or not row.user.active:
        return {"authenticated": False}
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    absolute = row.absolute_expires_at if row.absolute_expires_at.tzinfo else row.absolute_expires_at.replace(tzinfo=timezone.utc)
    if expires <= now or absolute <= now:
        return {"authenticated": False}
    return {"authenticated": True, **auth_json(row)}


@router.post("/logout", status_code=204)
def logout(response: Response, row: AuthSession = Depends(verify_csrf), db: Session = Depends(get_db)):
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.post("/logout-all", status_code=204)
def logout_all(response: Response, row: AuthSession = Depends(verify_csrf), db: Session = Depends(get_db)):
    db.query(AuthSession).filter(AuthSession.user_id == row.user_id, AuthSession.revoked_at.is_(None)).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()
    response.delete_cookie(COOKIE, path="/")

