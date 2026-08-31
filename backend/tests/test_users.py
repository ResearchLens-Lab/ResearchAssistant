from .conftest import USER_CREDENTIALS


async def test_get_profile(client, auth_headers):
    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == USER_CREDENTIALS["email"]


async def test_update_profile(client, auth_headers):
    resp = await client.patch(
        "/api/v1/users/me", json={"full_name": "Updated Name"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"

    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.json()["full_name"] == "Updated Name"


async def test_profile_requires_auth(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
