import pytest
from app.core.security import hash_password
from app.models import User, PasswordResetToken

AUTH_URL = "/api/v1/auth"


def test_cookie_auth_and_csrf_protection(client, db):
    # 1. Login sets cookies (access_token, refresh_token, csrf_token)
    login_res = client.post(f"{AUTH_URL}/login", data={"username": "alice", "password": "Password123!"})
    # Alice doesn't exist yet, register first
    reg_res = client.post(
        f"{AUTH_URL}/register",
        json={"email": "alice@example.com", "username": "alice", "password": "Password123!", "first_name": "Alice", "last_name": "Smith"},
    )
    assert reg_res.status_code == 201

    login_res = client.post(f"{AUTH_URL}/login", data={"username": "alice", "password": "Password123!"})
    assert login_res.status_code == 200
    assert "access_token" not in login_res.json()
    assert "refresh_token" not in login_res.json()
    assert login_res.json()["authenticated"] is True
    assert login_res.json()["expires_in"] == 3600
    cookies = login_res.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    assert "csrf_token" in cookies

    csrf_token = cookies["csrf_token"]

    # 2. Authenticated GET using cookies works without CSRF header (safe method)
    me_res = client.get(f"{AUTH_URL}/me", cookies={"access_token": cookies["access_token"]})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "alice"

    # 3. State-changing request with cookie but WITHOUT CSRF token fails with 403
    post_no_csrf = client.post(
        f"{AUTH_URL}/change-password",
        json={"current_password": "Password123!", "new_password": "NewPassword456!", "confirm_new_password": "NewPassword456!"},
        cookies={"access_token": cookies["access_token"], "csrf_token": csrf_token},
    )
    assert post_no_csrf.status_code == 403
    assert "CSRF" in post_no_csrf.json()["detail"]

    # 4. State-changing request with matching CSRF header succeeds
    change_res = client.post(
        f"{AUTH_URL}/change-password",
        json={"current_password": "Password123!", "new_password": "NewPassword456!", "confirm_new_password": "NewPassword456!"},
        headers={"X-CSRF-Token": csrf_token},
        cookies={"access_token": cookies["access_token"], "csrf_token": csrf_token},
    )
    assert change_res.status_code == 200
    assert change_res.json()["detail"] == "Password changed successfully"

    # 5. Verify new password works
    new_login = client.post(f"{AUTH_URL}/login", data={"username": "alice", "password": "NewPassword456!"})
    assert new_login.status_code == 200


def test_refresh_token_rotation_and_revocation(client, db):
    # Register and login
    client.post(
        f"{AUTH_URL}/register",
        json={"email": "bob@example.com", "username": "bob", "password": "Password123!", "first_name": "Bob", "last_name": "Jones"},
    )
    login_res = client.post(f"{AUTH_URL}/login", data={"username": "bob", "password": "Password123!"})
    cookies = login_res.cookies
    refresh_token = cookies["refresh_token"]

    # Refresh token endpoint with cookie
    refresh_res = client.post(f"{AUTH_URL}/refresh", cookies={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    assert "access_token" not in refresh_res.json()
    assert "refresh_token" not in refresh_res.json()
    assert refresh_res.json()["authenticated"] is True
    assert refresh_res.json()["expires_in"] == 3600
    new_cookies = refresh_res.cookies
    new_refresh_token = new_cookies["refresh_token"]
    assert new_refresh_token != refresh_token  # Rotated!

    # Old refresh token is revoked
    old_res = client.post(f"{AUTH_URL}/refresh", cookies={"refresh_token": refresh_token})
    assert old_res.status_code == 401

    # Logout revokes refresh token
    logout_res = client.post(
        f"{AUTH_URL}/logout",
        cookies={"access_token": new_cookies["access_token"], "refresh_token": new_refresh_token},
    )
    assert logout_res.status_code == 200

    # Using revoked token after logout fails
    after_logout_res = client.post(f"{AUTH_URL}/refresh", cookies={"refresh_token": new_refresh_token})
    assert after_logout_res.status_code == 401


def test_password_reset_flow(client, db):
    # Register carol
    client.post(
        f"{AUTH_URL}/register",
        json={"email": "carol@example.com", "username": "carol", "password": "OldPassword123!", "first_name": "Carol", "last_name": "Danvers"},
    )

    # 1. Request password reset (does not leak email existence)
    forgot_res = client.post(f"{AUTH_URL}/forgot-password", json={"email": "carol@example.com"})
    assert forgot_res.status_code == 200
    assert "password reset process" in forgot_res.json()["detail"]
    assert "token" not in forgot_res.json()

    # 2. In test environment, get raw reset token via test helper / auth_service
    from app.services.auth_service import initiate_password_reset
    raw_token = initiate_password_reset(db, "carol@example.com")
    assert raw_token is not None

    # Invalid reset token returns 400
    bad_res = client.post(
        f"{AUTH_URL}/reset-password",
        json={"token": "invalid-token", "new_password": "NewSecret123!", "confirm_new_password": "NewSecret123!"},
    )
    assert bad_res.status_code == 400
    assert "Invalid or expired" in bad_res.json()["detail"]

    # 3. Valid reset token succeeds
    reset_res = client.post(
        f"{AUTH_URL}/reset-password",
        json={"token": raw_token, "new_password": "NewSecret123!", "confirm_new_password": "NewSecret123!"},
    )
    assert reset_res.status_code == 200
    assert "reset successfully" in reset_res.json()["detail"]

    # 4. Token cannot be reused (single-use)
    reuse_res = client.post(
        f"{AUTH_URL}/reset-password",
        json={"token": raw_token, "new_password": "AnotherSecret123!", "confirm_new_password": "AnotherSecret123!"},
    )
    assert reuse_res.status_code == 400
    assert "Invalid or expired" in reuse_res.json()["detail"]

    # 5. Login works with new password
    login_new = client.post(f"{AUTH_URL}/login", data={"username": "carol", "password": "NewSecret123!"})
    assert login_new.status_code == 200


def test_sensitive_credentials_never_logged(client, db, caplog):
    import logging
    caplog.set_level(logging.DEBUG)

    # 1. Register
    reg_password = "SecretPassword123!"
    client.post(
        f"{AUTH_URL}/register",
        json={"email": "david@example.com", "username": "david", "password": reg_password, "first_name": "David", "last_name": "Miller"},
    )

    # 2. Login
    login_res = client.post(f"{AUTH_URL}/login", data={"username": "david", "password": reg_password})
    assert login_res.status_code == 200
    raw_refresh = login_res.cookies["refresh_token"]

    # 3. Forgot password
    from app.services.auth_service import initiate_password_reset
    raw_reset_token = initiate_password_reset(db, "david@example.com")
    assert raw_reset_token is not None

    # 4. Reset password
    client.post(
        f"{AUTH_URL}/reset-password",
        json={"token": raw_reset_token, "new_password": "BrandNewPassword123!", "confirm_new_password": "BrandNewPassword123!"},
    )

    # Verify no log record contains raw reset token, raw refresh token, raw password or hash
    logged_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert raw_reset_token not in logged_text
    assert raw_refresh not in logged_text
    assert reg_password not in logged_text
    assert "BrandNewPassword123!" not in logged_text
    # Ensure no bcrypt hash logged
    assert "$2b$" not in logged_text


