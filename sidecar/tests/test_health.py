def test_health_requires_session_token(app_client):
    response = app_client.get("/v1/health")
    assert response.status_code == 401


def test_health_returns_protocol(app_client, auth_headers):
    response = app_client.get("/v1/health", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["protocolVersion"] == "1"


def test_diagnostics_excludes_secrets(app_client, auth_headers):
    response = app_client.get("/v1/system/diagnostics", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["appVersion"] == "0.1.0"
    assert body["protocolVersion"] == "1"
    assert body["apiKeyStorage"]
    assert "session" not in str(body).lower()
    assert "token" not in str(body).lower()
