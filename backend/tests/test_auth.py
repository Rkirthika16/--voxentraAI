import pytest
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token


def test_password_hashing():
    pwd = "SecurePassword@123"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_lifecycle():
    token = create_access_token(subject=42, role="CITIZEN")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "CITIZEN"


def test_register_citizen_success(client):
    payload = {
        "full_name": "Ravi Kumar",
        "email": "ravi.kumar@example.com",
        "password": "Password@123",
        "phone": "9876501234"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["email"] == "ravi.kumar@example.com"
    assert data["role"] == "CITIZEN"


def test_register_duplicate_email_fails(client):
    payload = {
        "full_name": "Duplicate User",
        "email": "citizen@voxentra.tn.gov.in",
        "password": "Password@123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_login_success(client):
    payload = {
        "email": "citizen@voxentra.tn.gov.in",
        "password": "Citizen@123"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "CITIZEN"


def test_login_invalid_password(client):
    payload = {
        "email": "citizen@voxentra.tn.gov.in",
        "password": "WrongPassword!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


def test_get_me_authenticated(client, citizen_headers):
    response = client.get("/api/v1/auth/me", headers=citizen_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "citizen@voxentra.tn.gov.in"
