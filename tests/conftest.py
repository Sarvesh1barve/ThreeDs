import os
from pathlib import Path

TEST_DATA = Path(__file__).parent / ".data"
TEST_DATA.mkdir(exist_ok=True)
os.environ.update({
    "APP_ENV": "test",
    "APP_SECRET": "test-secret-is-long-enough-and-never-production",
    "DATA_DIR": str(TEST_DATA),
    "DATABASE_URL": f"sqlite:///{(TEST_DATA / 'test.db').as_posix()}",
    "COOKIE_SECURE": "false",
    "BASE_URL": "http://testserver",
    "ALLOWED_ORIGINS": "http://testserver",
})

import pytest
from fastapi.testclient import TestClient
from backend.app.db import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import User
from backend.app.security import hash_password


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app):
        pass
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_credentials():
    with SessionLocal() as db:
        db.add(User(full_name="Event Admin", phone="+919876543210", password_hash=hash_password("correct horse battery"), role="ADMIN"))
        db.commit()
    return {"phone": "+919876543210", "password": "correct horse battery"}


def register(client, phone="9876500001"):
    response = client.post("/api/auth/register", json={"full_name": "Exhibition Guest", "phone": phone, "password": "very-secure-pass"})
    assert response.status_code == 201, response.text
    return response.json()


def csrf_headers(auth):
    return {"X-CSRF-Token": auth["csrf_token"], "Origin": "http://testserver"}

