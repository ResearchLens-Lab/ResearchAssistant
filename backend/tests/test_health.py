async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "ResearchAssistant"


async def test_health_ready(client):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


async def test_request_id_header_present(client):
    resp = await client.get("/health")
    assert resp.headers.get("X-Request-ID")


async def test_request_id_header_is_preserved(client):
    resp = await client.get("/health", headers={"X-Request-ID": "req_custom_123"})
    assert resp.headers["X-Request-ID"] == "req_custom_123"


async def test_error_shape_for_unknown_route(client):
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"]
