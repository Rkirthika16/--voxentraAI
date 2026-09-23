def test_create_complaint_authenticated(client, citizen_headers):
    payload = {
        "title": "Water leakage in street",
        "description": "The main drinking water pipeline is leaking heavily near Gandhipuram bus stand.",
        "category": "Water",
        "location": "Gandhipuram Central Bus Stand, Coimbatore",
        "priority": "HIGH",
        "language": "English"
    }
    response = client.post("/api/v1/complaints", json=payload, headers=citizen_headers)
    assert response.status_code == 201
    data = response.json()
    assert "complaint_number" in data
    assert data["complaint_number"].startswith(("VX-", "VOX-"))
    assert data["category"] == "Water"
    assert data["status"] == "SUBMITTED"
    assert data["citizen_name"] == "Murugan Citizen"


def test_list_my_complaints(client, citizen_headers):
    response = client.get("/api/v1/complaints/my", headers=citizen_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_complaint_details_by_id(client, citizen_headers):
    # First create
    payload = {
        "description": "Streetlight bulb broken in Gandhipuram",
        "category": "Streetlights",
        "location": "Gandhipuram"
    }
    create_res = client.post("/api/v1/complaints", json=payload, headers=citizen_headers)
    complaint_id = create_res.json()["id"]

    # Then retrieve
    detail_res = client.get(f"/api/v1/complaints/{complaint_id}", headers=citizen_headers)
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["id"] == complaint_id
    assert "history" in data
    assert len(data["history"]) >= 1
