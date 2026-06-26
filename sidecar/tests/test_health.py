def test_health_requires_session_token(app_client):
    response = app_client.get("/v1/health")
    assert response.status_code == 401


def test_health_returns_protocol(app_client, auth_headers):
    response = app_client.get("/v1/health", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["protocolVersion"] == "1"
