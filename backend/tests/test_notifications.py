def test_notification_flow(client, citizen_headers, officer_headers):
    # 1. Citizen creates complaint -> receives submission notification
    create_res = client.post(
        "/api/v1/complaints",
        json={
            "description": "Streetlight flickering at night",
            "category": "Streetlights"
        },
        headers=citizen_headers
    )
    complaint_id = create_res.json()["id"]

    notif_res = client.get("/api/v1/notifications", headers=citizen_headers)
    assert notif_res.status_code == 200
    notifications = notif_res.json()
    assert len(notifications) >= 1
    
    first_notif = notifications[0]
    notif_id = first_notif["id"]

    # 2. Mark notification as read
    read_res = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=citizen_headers)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True
