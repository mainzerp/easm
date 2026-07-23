import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://easm:easm@localhost:5432/easm_test",
)

from db import Base, SessionLocal, engine  # noqa: E402
import auth  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    auth.load_credentials()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_session(client: TestClient) -> str:
    from auth import SESSION_COOKIE
    import secrets

    resp = client.get("/api/auth/check")
    data = resp.json()
    password = secrets.token_urlsafe(16)
    auth.set_password_hash(auth.hash_password(password))

    resp = client.post("/api/auth/login", json={"password": password})
    if resp.status_code != 200:
        return ""
    return resp.cookies.get(SESSION_COOKIE, "")
