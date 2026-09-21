def test_citizen_cannot_access_admin_stats(client, citizen_headers):
    response = client.get("/api/v1/admin/stats", headers=citizen_headers)
    assert response.status_code == 403


def test_citizen_cannot_access_user_list(client, citizen_headers):
    response = client.get("/api/v1/users", headers=citizen_headers)
    assert response.status_code == 403


def test_citizen_cannot_create_officer(client, citizen_headers):
    payload = {
        "full_name": "Fake Officer",
        "email": "fake.officer@example.com",
        "password": "Password@123",
        "department_id": 1
    }
    response = client.post("/api/v1/users/officer", json=payload, headers=citizen_headers)
    assert response.status_code == 403


def test_admin_can_access_stats(client, admin_headers):
    response = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_complaints" in data
    assert "departments" in data
