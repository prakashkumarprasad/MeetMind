# Tests for authentication flows: signup, login, Google OAuth, refresh rotation, and rate limiting.

"""
Covers signup, login, refresh, and Google OAuth (app/api/v1/auth.py).

Google's real verify_oauth2_token makes a network call to Google to fetch
their public keys — tests must never do that (slow, flaky offline, and
not actually testing your code). It's mocked at its usage site,
app.api.v1.auth.google_id_token.verify_oauth2_token, to return a fake
decoded payload instead. This tests YOUR account-creation/linking logic,
not Google's SDK — which is already Google's job to test, not yours.
"""
import uuid

VALID_PASSWORD = "SuperSecurePassword123"

XHR_HEADERS = {"X-Requested-With": "XMLHttpRequest"}

def test_signup_creates_user_and_returns_token(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "newuser@example.com", "password": VALID_PASSWORD, "full_name": "New User"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

    assert "refresh_token" in response.cookies

def test_signup_duplicate_email_rejected(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "dupe@example.com", "password": VALID_PASSWORD},
    )
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "dupe@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 400

def test_signup_short_password_rejected(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "shortpw@example.com", "password": "short1"},
    )

    assert response.status_code == 422

def test_login_with_correct_password_succeeds(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "logintest@example.com", "password": VALID_PASSWORD},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "logintest@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_with_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "wrongpw@example.com", "password": VALID_PASSWORD},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "TotallyWrongPassword123"},
    )

    assert response.status_code == 401

def test_login_rate_limit_only_counts_failures(client):
    """
    Successful logins must NOT consume the rate-limit budget.
    After several successful logins, the user should still be able to
    log in again — the counter must only advance on *failed* attempts.
    """
    client.post(
        "/api/v1/auth/signup",
        json={"email": "ratelimitcheck@example.com", "password": VALID_PASSWORD},
    )

    for _ in range(3):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimitcheck@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 200

    statuses = []
    for _ in range(6):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimitcheck@example.com", "password": "WrongPass123"},
        )
        statuses.append(resp.status_code)

    assert all(s == 401 for s in statuses[:5])
    assert all(s == 429 for s in statuses[5:])

def test_login_rate_limit_triggers_on_failed_attempts(client):
    """
    Repeated failed logins for the same email must eventually return 429.
    """
    client.post(
        "/api/v1/auth/signup",
        json={"email": "bruteforce@example.com", "password": VALID_PASSWORD},
    )

    statuses = []
    for _ in range(7):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "bruteforce@example.com", "password": "WrongPass123"},
        )
        statuses.append(resp.status_code)

    assert all(s == 401 for s in statuses[:5])
    assert all(s == 429 for s in statuses[5:])

def test_login_nonexistent_email_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doesnotexist@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 401

def test_login_google_only_account_has_no_password_rejected(client, db_session):
    """
    A user who only ever signed up via Google has hashed_password=None.
    Logging in with a password against that account must fail cleanly,
    not crash on `verify_password(pw, None)`.
    """
    from app.models.user import User

    user = User(email="googleonly@example.com", google_id="fake-google-sub-123", hashed_password=None)
    db_session.add(user)
    db_session.flush()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "googleonly@example.com", "password": VALID_PASSWORD},
    )

    assert response.status_code == 401

def test_refresh_with_valid_cookie_issues_new_token(client):
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": "refreshtest@example.com", "password": VALID_PASSWORD},
    )
    first_token = signup_response.json()["access_token"]

    refresh_response = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)

    assert refresh_response.status_code == 200
    new_token = refresh_response.json()["access_token"]
    assert new_token != first_token

def test_refresh_without_cookie_rejected(client):
    response = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)

    assert response.status_code == 401

def _fake_google_payload(**overrides):
    payload = {
        "sub": "fake-google-sub-" + str(uuid.uuid4()),
        "email": "googleuser@example.com",
        "email_verified": True,
        "name": "Google User",
    }
    payload.update(overrides)
    return payload

def test_google_auth_creates_new_user(client, monkeypatch):
    fake_payload = _fake_google_payload()
    monkeypatch.setattr(
        "app.api.v1.auth.google_id_token.verify_oauth2_token",
        lambda credential, request, client_id: fake_payload,
    )

    response = client.post("/api/v1/auth/google", json={"credential": "fake-jwt-doesnt-matter"})

    assert response.status_code == 200
    assert "access_token" in response.json()

def test_google_auth_links_existing_password_account(client, monkeypatch, db_session):
    """
    A user who signed up with email/password, then logs in with Google
    using the SAME email, should be linked to the existing account —
    not create a duplicate user row.
    """
    from app.models.user import User

    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": "linktest@example.com", "password": VALID_PASSWORD},
    )
    assert signup_response.status_code == 200

    fake_payload = _fake_google_payload(email="linktest@example.com")
    monkeypatch.setattr(
        "app.api.v1.auth.google_id_token.verify_oauth2_token",
        lambda credential, request, client_id: fake_payload,
    )

    google_response = client.post("/api/v1/auth/google", json={"credential": "fake-jwt"})
    assert google_response.status_code == 200

    matching_users = db_session.query(User).filter(User.email == "linktest@example.com").all()
    assert len(matching_users) == 1
    assert matching_users[0].google_id == fake_payload["sub"]

def test_google_auth_unverified_email_rejected(client, monkeypatch):
    fake_payload = _fake_google_payload(email_verified=False)
    monkeypatch.setattr(
        "app.api.v1.auth.google_id_token.verify_oauth2_token",
        lambda credential, request, client_id: fake_payload,
    )

    response = client.post("/api/v1/auth/google", json={"credential": "fake-jwt"})

    assert response.status_code == 401

def test_google_auth_returning_user_no_duplicate(client, monkeypatch, db_session):
    from app.models.user import User

    fake_payload = _fake_google_payload(email="returning@example.com")
    monkeypatch.setattr(
        "app.api.v1.auth.google_id_token.verify_oauth2_token",
        lambda credential, request, client_id: fake_payload,
    )

    first_response = client.post("/api/v1/auth/google", json={"credential": "fake-jwt-1"})
    second_response = client.post("/api/v1/auth/google", json={"credential": "fake-jwt-2"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    matching_users = db_session.query(User).filter(User.email == "returning@example.com").all()
    assert len(matching_users) == 1
