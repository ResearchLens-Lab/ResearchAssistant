from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.models.user import User

from .conftest import SECOND_USER_CREDENTIALS, USER_CREDENTIALS, register_and_login


async def test_register(client):
    resp = await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == USER_CREDENTIALS["email"]
    assert body["username"] == USER_CREDENTIALS["username"]
    assert body["is_active"] is True
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email(client):
    resp = await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    assert resp.status_code == 201
    resp = await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_register_short_password_rejected(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "a@b.com", "username": "shortname", "password": "short"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login(client):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_CREDENTIALS["email"],
            "password": USER_CREDENTIALS["password"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == USER_CREDENTIALS["username"]
    assert "hashed_password" not in body["user"]


async def test_username_is_normalized_and_username_login_works(client):
    registration = {**USER_CREDENTIALS, "username": "Abhay.Kumar"}
    created = await client.post("/api/v1/auth/register", json=registration)
    assert created.status_code == 201
    assert created.json()["username"] == "abhay.kumar"
    login = await client.post("/api/v1/auth/login", json={"identifier": "ABHAY.KUMAR", "password": USER_CREDENTIALS["password"]})
    assert login.status_code == 200


async def test_duplicate_username_conflicts_case_insensitively(client):
    assert (await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)).status_code == 201
    duplicate = {**SECOND_USER_CREDENTIALS, "username": "ABHAY_KUMAR"}
    response = await client.post("/api/v1/auth/register", json=duplicate)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_TAKEN"
    assert SECOND_USER_CREDENTIALS["email"] not in response.text


async def test_email_login_remains_compatible(client):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    response = await client.post("/api/v1/auth/login", json={"email": USER_CREDENTIALS["email"], "password": USER_CREDENTIALS["password"]})
    assert response.status_code == 200


async def test_legacy_account_without_username_keeps_email_login(client, db_engine):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(update(User).where(User.email == USER_CREDENTIALS["email"]).values(username=None))
        await session.commit()
    response = await client.post("/api/v1/auth/login", json={"identifier": USER_CREDENTIALS["email"], "password": USER_CREDENTIALS["password"]})
    assert response.status_code == 200


async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": USER_CREDENTIALS["email"], "password": "wrong-password-1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == USER_CREDENTIALS["email"]


async def test_me_without_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_invalid_token(client):
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


async def test_refresh_token_cannot_be_used_as_access_token(client):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_CREDENTIALS["email"],
            "password": USER_CREDENTIALS["password"],
        },
    )
    refresh_token = login.json()["refresh_token"]
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp.status_code == 401


async def test_inactive_user_rejected(client, db_engine):
    headers = await register_and_login(client, USER_CREDENTIALS)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            update(User)
            .where(User.email == USER_CREDENTIALS["email"])
            .values(is_active=False)
        )
        await session.commit()
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_refresh_rotation(client):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_CREDENTIALS["email"],
            "password": USER_CREDENTIALS["password"],
        },
    )
    old_refresh = login.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != old_refresh

    # The rotated (old) token must be rejected on reuse.
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await client.post("/api/v1/auth/register", json=USER_CREDENTIALS)
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_CREDENTIALS["email"],
            "password": USER_CREDENTIALS["password"],
        },
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 204

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
