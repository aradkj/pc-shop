from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"

PAYLOAD = {
    "email": "user@example.com",
    "username": "user123",
    "password": "Password123!",
    "first_name": "John",
    "last_name": "Doe",
}


def login(client, identifier, password):
    return client.post(LOGIN_URL, data={"username": identifier, "password": password})


# ------------------------------------------------------------------ registration


def test_register_success(client):
    response = client.post(REGISTER_URL, json=PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["username"] == "user123"
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"
    assert body["role"] == "customer"
    assert body["is_active"] is True
    assert isinstance(body["id"], int)
    assert "password" not in body and "hashed_password" not in body


def test_register_stores_a_bcrypt_hash_never_the_password(client, db):
    client.post(REGISTER_URL, json=PAYLOAD)

    user = db.scalar(select(User))
    assert user.hashed_password != PAYLOAD["password"]
    assert user.hashed_password.startswith("$2")  # bcrypt
    assert verify_password(PAYLOAD["password"], user.hashed_password)


def test_register_normalizes_email_and_username_to_lowercase(client):
    response = client.post(REGISTER_URL, json={**PAYLOAD, "email": "John.Doe@Example.COM", "username": "JohnDoe"})

    assert response.json()["email"] == "john.doe@example.com"
    assert response.json()["username"] == "johndoe"


def test_register_ignores_a_client_supplied_role(client, db):
    response = client.post(REGISTER_URL, json={**PAYLOAD, "role": "admin", "is_active": False})

    assert response.status_code == 201
    user = db.scalar(select(User))
    assert user.role == UserRole.CUSTOMER
    assert user.is_active is True


def test_register_duplicate_email(client):
    client.post(REGISTER_URL, json=PAYLOAD)

    response = client.post(REGISTER_URL, json={**PAYLOAD, "username": "another", "email": "USER@example.com"})

    assert response.status_code == 409
    assert "email" in response.json()["detail"].lower()


def test_register_duplicate_username(client):
    client.post(REGISTER_URL, json=PAYLOAD)

    response = client.post(REGISTER_URL, json={**PAYLOAD, "email": "another@example.com", "username": "USER123"})

    assert response.status_code == 409
    assert "username" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("username", "ab"),
        ("username", "has space"),
        ("username", "user@name"),
        ("password", "short"),
        ("first_name", ""),
        ("last_name", "   "),
    ],
)
def test_register_validation_errors(client, field, value):
    response = client.post(REGISTER_URL, json={**PAYLOAD, field: value})

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors[0]["loc"] == ["body", field]
    assert set(errors[0]) == {"loc", "msg", "type"}  # no "input"/"ctx": nothing is echoed back


def test_register_missing_fields(client):
    response = client.post(REGISTER_URL, json={"email": "user@example.com"})

    assert response.status_code == 422


def test_register_validation_error_does_not_echo_the_password(client):
    response = client.post(REGISTER_URL, json={**PAYLOAD, "email": "bad", "password": "SuperSecret1"})

    assert response.status_code == 422
    assert "SuperSecret1" not in response.text


def test_register_rejects_passwords_longer_than_bcrypt_limit(client):
    response = client.post(REGISTER_URL, json={**PAYLOAD, "password": "é" * 40})  # 80 bytes in UTF-8

    assert response.status_code == 422


# ------------------------------------------------------------------------ login


def test_login_success(client, customer):
    response = login(client, "customer@example.com", "Password123!")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600

    settings = get_settings()
    payload = jwt.decode(body["access_token"], settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == str(customer.id)
    assert payload["exp"] - payload["iat"] == 3600


def test_login_with_username_and_mixed_case_email(client, customer):
    assert login(client, "customer", "Password123!").status_code == 200
    assert login(client, "Customer@Example.com", "Password123!").status_code == 200


def test_login_invalid_password(client, customer):
    response = login(client, "customer@example.com", "WrongPassword1!")

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_unknown_user_gives_the_same_error(client):
    response = login(client, "nobody@example.com", "Password123!")

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_login_inactive_account_is_forbidden(client, create_user):
    create_user(is_active=False)

    response = login(client, "customer@example.com", "Password123!")

    assert response.status_code == 403


def test_login_requires_form_fields(client):
    assert client.post(LOGIN_URL, data={"username": "customer"}).status_code == 422


# ------------------------------------------------------------- current user / JWT


def test_get_current_user(client, customer, customer_headers):
    response = client.get(ME_URL, headers=customer_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == customer.id
    assert body["email"] == "customer@example.com"
    assert body["role"] == "customer"
    assert "hashed_password" not in body


def test_get_current_user_with_token_from_login(client, customer):
    token = login(client, "customer@example.com", "Password123!").json()["access_token"]

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "customer"


def test_me_requires_authentication(client):
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_garbage_token_is_rejected(client):
    response = client.get(ME_URL, headers={"Authorization": "Bearer not.a.jwt"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


def test_expired_token_is_rejected(client, customer):
    token = create_access_token(str(customer.id), expires_delta=timedelta(seconds=-5))

    assert client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_with_another_key_is_rejected(client, customer):
    expires = datetime.now(UTC) + timedelta(minutes=5)
    forged = jwt.encode({"sub": str(customer.id), "exp": expires}, "x" * 40, algorithm="HS256")

    assert client.get(ME_URL, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_unsigned_token_is_rejected(client, customer):
    expires = datetime.now(UTC) + timedelta(minutes=5)
    unsigned = jwt.encode({"sub": str(customer.id), "exp": expires}, None, algorithm="none")

    assert client.get(ME_URL, headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_token_without_subject_is_rejected(client):
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=5)
    token = jwt.encode({"exp": expires}, settings.secret_key, algorithm=settings.algorithm)

    assert client.get(ME_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_of_a_deleted_user_is_rejected(client, db, customer, customer_headers):
    db.delete(customer)
    db.commit()

    assert client.get(ME_URL, headers=customer_headers).status_code == 401


def test_token_of_a_disabled_user_is_rejected(client, db, customer, customer_headers):
    customer.is_active = False
    db.commit()

    assert client.get(ME_URL, headers=customer_headers).status_code == 403


# ---------------------------------------------------------------- password hashing


def test_password_hashing_is_salted_and_verifiable():
    first, second = hash_password("Password123!"), hash_password("Password123!")

    assert first != second  # random salt
    assert verify_password("Password123!", first)
    assert not verify_password("password123!", first)


def test_verify_password_never_raises_on_bad_input():
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("x" * 100, hash_password("Password123!")) is False
