import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.db import SessionLocal
from backend.app.models import User
from backend.app.security import hash_password, normalize_phone
from backend.app.services.seed import bootstrap


def main():
    parser = argparse.ArgumentParser(description="Create or update the first Three D's administrator")
    parser.add_argument("--phone")
    parser.add_argument("--name", default="Three D's Admin")
    args = parser.parse_args()
    phone_raw = args.phone or input("Admin Indian mobile number: ")
    password = os.environ.get("THREEDS_ADMIN_PASSWORD") or getpass.getpass("Strong admin password (12+ chars): ")
    if len(password) < 12: raise SystemExit("Password must be at least 12 characters.")
    with SessionLocal() as db:
        bootstrap(db)
        phone = normalize_phone(phone_raw)
        user = db.query(User).filter(User.phone == phone).first()
        if user and user.role != "ADMIN": raise SystemExit("That number belongs to a customer; use another number.")
        if not user:
            user = User(full_name=args.name, phone=phone, password_hash=hash_password(password), role="ADMIN")
            db.add(user)
        else:
            user.password_hash = hash_password(password); user.active = True
        db.commit()
        print(f"Administrator ready: {phone}. No password was printed or stored in source.")


if __name__ == "__main__": main()

