import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://easm:easm@localhost:5432/easm_test",
)

from main import app  # noqa: E402
import auth  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_auth():
    os.environ.pop("EASM_ADMIN_PASSWORD", None)
    os.environ.pop("EASM_ADMIN_PASSWORD_HASH", None)
    auth.load_credentials()
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fresh_pw() -> str:
    import secrets

    pw = secrets.token_urlsafe(16)
    auth.set_password_hash(auth.hash_password(pw))
    return pw


@pytest.fixture(autouse=True)
def _reset_totp():
    auth.set_totp_secret(None)
    yield
