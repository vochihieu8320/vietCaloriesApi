def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_includes_healthz(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/healthz" in response.json()["paths"]
