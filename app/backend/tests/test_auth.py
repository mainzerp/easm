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


def test_login_valid(client):
    import secrets

    pw = secrets.token_urlsafe(16)
    from auth import set_password_hash, hash_password

    set_password_hash(hash_password(pw))
    resp = client.post("/api/auth/login", json={"password": pw})
    assert resp.status_code == 200
    assert "easm_session" in resp.cookies


def test_change_password_requires_current(client):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "new"},
    )
    assert resp.status_code == 401


def test_totp_setup_no_password(client):
    resp = client.post("/api/auth/totp/setup", json={"current_password": ""})
    assert resp.status_code == 401


def test_totp_setup_blocks_if_enabled(client):
    import secrets

    pw = secrets.token_urlsafe(16)
    from auth import set_password_hash, hash_password, set_totp_secret

    set_password_hash(hash_password(pw))
    set_totp_secret("JBSWY3DPEHPK3PXP")

    resp = client.post("/api/auth/totp/setup", json={"current_password": pw})
    assert resp.status_code == 400
