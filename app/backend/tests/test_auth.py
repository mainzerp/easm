import auth


def test_auth_user_endpoint(client):
    resp = client.get("/api/auth/user")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["totp_enabled"] is False


def test_auth_check_unauthenticated(client):
    resp = client.get("/api/auth/check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False


def test_login_no_password(client):
    resp = client.post("/api/auth/login", json={"password": ""})
    assert resp.status_code == 401


def test_login_valid(client, fresh_pw):
    resp = client.post("/api/auth/login", json={"password": fresh_pw})
    assert resp.status_code == 200
    assert "easm_session" in resp.cookies


def test_change_password_requires_current(client):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "new"},
    )
    assert resp.status_code == 401


def test_change_password_success(client, fresh_pw):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": fresh_pw, "new_password": "newsecurepw"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_totp_setup_no_password(client):
    resp = client.post("/api/auth/totp/setup", json={"current_password": ""})
    assert resp.status_code == 401


def test_totp_setup_blocks_if_enabled(client, fresh_pw):
    auth.set_totp_secret("JBSWY3DPEHPK3PXP")
    resp = client.post("/api/auth/totp/setup", json={"current_password": fresh_pw})
    assert resp.status_code == 400


def test_totp_setup_returns_qr(client, fresh_pw):
    resp = client.post("/api/auth/totp/setup", json={"current_password": fresh_pw})
    assert resp.status_code == 200
    data = resp.json()
    assert "secret" in data
    assert "qr_uri" in data
    assert data["qr_uri"].startswith("data:image/svg+xml")


def test_totp_verify_succeeds(client, fresh_pw):
    import pyotp

    resp = client.post("/api/auth/totp/setup", json={"current_password": fresh_pw})
    secret = resp.json()["secret"]
    code = pyotp.TOTP(secret).now()
    resp2 = client.post(
        "/api/auth/totp/verify",
        json={"current_password": fresh_pw, "code": code},
    )
    assert resp2.status_code == 200
    assert resp2.json()["totp_enabled"] is True
    assert auth.totp_enabled() is True


def test_totp_disable(client, fresh_pw):
    auth.set_totp_secret("JBSWY3DPEHPK3PXP")
    resp = client.post(
        "/api/auth/totp/disable",
        json={"current_password": fresh_pw},
    )
    assert resp.status_code == 200
    assert resp.json()["totp_enabled"] is False
    assert auth.totp_enabled() is False
