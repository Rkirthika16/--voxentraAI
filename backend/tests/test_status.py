def test_status_lifecycle_and_history(client, citizen_headers, officer_headers):
    # 1. Citizen creates complaint
    create_res = client.post(
        "/api/v1/complaints",
        json={
            "title": "Pipeline burst",
            "description": "Clean water overflowing across pavement",
            "category": "Water"
        },
        headers=citizen_headers
    )
    complaint_id = create_res.json()["id"]
    assert create_res.json()["status"] == "SUBMITTED"

    # 2. Officer moves to UNDER_REVIEW
    update_res = client.patch(
        f"/api/v1/complaints/{complaint_id}/status",
        json={"status": "UNDER_REVIEW", "note": "Assigned inspection team"},
        headers=officer_headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "UNDER_REVIEW"

    # 3. Officer moves to IN_PROGRESS
    update_res2 = client.patch(
        f"/api/v1/complaints/{complaint_id}/status",
        json={"status": "IN_PROGRESS", "note": "Repair crew deployed"},
        headers=officer_headers
    )
    assert update_res2.status_code == 200
    assert update_res2.json()["status"] == "IN_PROGRESS"

    # 4. Officer resolves
    update_res3 = client.patch(
        f"/api/v1/complaints/{complaint_id}/status",
        json={"status": "RESOLVED", "note": "Leak fixed and tested"},
        headers=officer_headers
    )
    assert update_res3.status_code == 200
    assert update_res3.json()["status"] == "RESOLVED"

    # 5. Check history audit log
    hist_res = client.get(f"/api/v1/complaints/{complaint_id}/history", headers=officer_headers)
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 4
