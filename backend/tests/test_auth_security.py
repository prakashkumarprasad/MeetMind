# Security tests: refresh-token reuse detection, logout revocation, and CSRF header enforcement.

"""
Covers the refresh-token *family* revocation built in auth.py (the known gap:
a stolen refresh token used to work until it expired, with no server-side way
to detect or kill it). This is the highest-value hardening in the security
audit:

  * logout() must revoke the family server-side — a captured cookie replayed
    after logout must be refused, not just the cookie cleared client-side.
  * rotation must move the family's last_jti forward; replaying an *older*
    (already-rotated) token is the stolen-token signal and must revoke the
    whole family.
  * signup now has a per-IP rate limit so a script can't mint unbounded
    accounts (login already had one).
"""
import pytest

from app.api.v1.auth import SIGNUP_RATE_LIMIT_MAX

VALID_PASSWORD = "SuperSecurePassword123"

XHR_HEADERS = {"X-Requested-With": "XMLHttpRequest"}

def _signup(client, email):
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return client.cookies.get("refresh_token")

def test_logout_revokes_refresh_token_server_side(client):
    """After logout, replaying the old cookie gets 401 — not ignored."""
    _signup(client, "logoutsec@example.com")
    captured = client.cookies.get("refresh_token")
    assert captured

    out = client.post("/api/v1/auth/logout", headers=XHR_HEADERS)
    assert out.status_code == 200

    client.cookies.set("refresh_token", captured)
    refresh = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert refresh.status_code == 401
    assert "revoked" in refresh.json()["detail"]

def test_stale_refresh_token_reuse_revokes_whole_family(client):
    """Replaying an already-rotated (stale) refresh token kills the family."""
    _signup(client, "reuse@example.com")
    t1 = client.cookies.get("refresh_token")

    r = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert r.status_code == 200
    t2 = client.cookies.get("refresh_token")
    assert t2 != t1

    client.cookies.set("refresh_token", t1)
    replay = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert replay.status_code == 401
    assert "reuse" in replay.json()["detail"]

    client.cookies.set("refresh_token", t2)
    replay2 = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert replay2.status_code == 401

def test_refresh_without_xhr_header_is_forbidden(client):
    """Missing custom header = 'not from our frontend' -> 403, before any
    cookie/token logic runs (the actual CSRF fix)."""
    _signup(client, "csrf-refresh@example.com")
    assert client.cookies.get("refresh_token")
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 403

def test_logout_without_xhr_header_is_forbidden(client):
    """A cross-origin form/submission can't carry the header, so logout
    without it must be refused rather than silently logging the user out."""
    _signup(client, "csrf-logout@example.com")
    assert client.cookies.get("refresh_token")
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 403

def test_refresh_with_wrong_xhr_value_is_forbidden(client):
    """Only the exact expected value passes — anything else is still 403."""
    _signup(client, "csrf-wrong@example.com")
    resp = client.post(
        "/api/v1/auth/refresh",
        headers={"X-Requested-With": "fetch"},
    )
    assert resp.status_code == 403

def test_normal_refresh_keeps_working_across_rotations(client):
    """Downstream of the above: a well-behaved token keeps refreshing."""
    _signup(client, "rotatesec@example.com")
    for _ in range(3):
        r = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
        assert r.status_code == 200
        assert "access_token" in r.json()

def test_signup_is_rate_limited_per_ip(client):
    """Mass account minting from one IP is throttled."""
    for i in range(SIGNUP_RATE_LIMIT_MAX):
        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": f"spam{i}@example.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": "spam-exceed@example.com", "password": VALID_PASSWORD},
    )
    assert resp.status_code == 429


def test_concurrent_refresh_rotation_is_tolerated_within_grace(client, monkeypatch):
    """
    Two tabs refreshing with the same token is a benign race, not theft. With the
    grace window raised, replaying the just-rotated (stale) token must still be
    accepted instead of revoking the whole family (which previously logged users
    out randomly).
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 3600)

    _signup(client, "race@example.com")
    t1 = client.cookies.get("refresh_token")

    r = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert r.status_code == 200

    # A concurrent tab still holding the pre-rotation token refreshes now.
    client.cookies.set("refresh_token", t1)
    r2 = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert r2.status_code == 200, r2.text
    assert "access_token" in r2.json()


def test_stale_replay_after_grace_revokes_family(client, monkeypatch):
    """
    When the replay falls outside the grace window it is treated as a genuine
    stolen-token replay and the whole family is revoked (security preserved).
    We simulate time passing by shrinking the window to -1 (never within grace).
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", -1)

    _signup(client, "latereplay@example.com")
    t1 = client.cookies.get("refresh_token")

    r = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert r.status_code == 200

    client.cookies.set("refresh_token", t1)
    replay = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert replay.status_code == 401
    assert "reuse" in replay.json()["detail"]


def test_logout_revokes_family_even_under_grace(client, monkeypatch):
    """Logout always revokes the family, regardless of the grace window."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 3600)

    _signup(client, "racelogout@example.com")
    token = client.cookies.get("refresh_token")

    out = client.post("/api/v1/auth/logout", headers=XHR_HEADERS)
    assert out.status_code == 200

    client.cookies.set("refresh_token", token)
    refresh = client.post("/api/v1/auth/refresh", headers=XHR_HEADERS)
    assert refresh.status_code == 401
    assert "revoked" in refresh.json()["detail"]
