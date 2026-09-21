def test_admin_stats_aggregation(client, admin_headers, citizen_headers):
    # Ensure at least one complaint exists
    client.post(
        "/api/v1/complaints",
        json={
            "description": "Garbage dump not cleared for 5 days",
            "category": "Sanitation/Garbage",
            "priority": "HIGH"
        },
        headers=citizen_headers
    )

    stats_res = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_complaints"] >= 1
    assert isinstance(stats["categories"], list)
    assert isinstance(stats["departments"], list)
    assert isinstance(stats["priorities"], list)
    assert len(stats["departments"]) == 8
