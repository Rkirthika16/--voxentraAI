def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["project"] == "VoxentraAI"
    assert data["database"] == "connected"
    assert "fallback_ai_active" in data


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "VoxentraAI"
    assert "/docs" in data["docs_url"]
