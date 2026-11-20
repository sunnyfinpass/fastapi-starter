from httpx import AsyncClient

from tests.conftest import PASSWORD, bearer

API = "/api/v1"


async def test_register_login_me(client: AsyncClient, make_user) -> None:
    tokens = await make_user()
    r = await client.get(f"{API}/users/me", headers=bearer(tokens))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "jane@example.com"
    assert body["role"] == "user"
    assert body["is_verified"] is False
    assert "hashed_password" not in body


async def test_duplicate_email_returns_409(client: AsyncClient, make_user) -> None:
    await make_user()
    r = await client.post(f"{API}/auth/register", json={"email": "JANE@example.com", "password": PASSWORD})
    assert r.status_code == 409


async def test_wrong_password_returns_401(client: AsyncClient, make_user) -> None:
    await make_user()
    r = await client.post(f"{API}/auth/login", data={"username": "jane@example.com", "password": "nope"})
    assert r.status_code == 401


async def test_protected_route_needs_token(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/users/me")).status_code == 401


async def test_refresh_rotation_and_reuse_detection(client: AsyncClient, make_user) -> None:
    t1 = await make_user()
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert r.status_code == 200
    t2 = r.json()
    assert t2["refresh_token"] != t1["refresh_token"]

    # replaying the old (already rotated) token is treated as theft...
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert r.status_code == 401
    # ...and revokes the whole session family, including the newest token
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": t2["refresh_token"]})
    assert r.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient, make_user) -> None:
    tokens = await make_user()
    r = await client.post(f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 204
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_logout_all(client: AsyncClient, make_user) -> None:
    tokens = await make_user()
    r = await client.post(f"{API}/auth/logout-all", headers=bearer(tokens))
    assert r.status_code == 204
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_change_password(client: AsyncClient, make_user) -> None:
    tokens = await make_user()
    r = await client.post(
        f"{API}/auth/change-password",
        headers=bearer(tokens),
        json={"current_password": "wrong", "new_password": "newpassword99"},
    )
    assert r.status_code == 400

    r = await client.post(
        f"{API}/auth/change-password",
        headers=bearer(tokens),
        json={"current_password": PASSWORD, "new_password": "newpassword99"},
    )
    assert r.status_code == 200
    # old sessions are dead, old password no longer works, new one does
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    r = await client.post(f"{API}/auth/login", data={"username": "jane@example.com", "password": PASSWORD})
    assert r.status_code == 401
    r = await client.post(f"{API}/auth/login", data={"username": "jane@example.com", "password": "newpassword99"})
    assert r.status_code == 200


async def test_password_reset_flow(client: AsyncClient, make_user, outbox) -> None:
    tokens = await make_user()
    r = await client.post(f"{API}/auth/forgot-password", json={"email": "jane@example.com"})
    assert r.status_code == 202
    token = outbox["reset"][0][1]

    r = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "brandnew4567"})
    assert r.status_code == 200
    # existing sessions revoked
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    r = await client.post(f"{API}/auth/login", data={"username": "jane@example.com", "password": "brandnew4567"})
    assert r.status_code == 200
    # single use
    r = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "another12345"})
    assert r.status_code == 401


async def test_forgot_password_unknown_email_same_response(client: AsyncClient, outbox) -> None:
    r = await client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 202
    assert outbox["reset"] == []


async def test_email_verification(client: AsyncClient, make_user, outbox) -> None:
    tokens = await make_user()
    token = outbox["verify"][0][1]
    r = await client.post(f"{API}/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    r = await client.get(f"{API}/users/me", headers=bearer(tokens))
    assert r.json()["is_verified"] is True
    # resend is rejected once verified
    r = await client.post(f"{API}/auth/resend-verification", headers=bearer(tokens))
    assert r.status_code == 400


async def test_special_tokens_cannot_be_used_as_access_tokens(
    client: AsyncClient, make_user, outbox
) -> None:
    await make_user()
    await client.post(f"{API}/auth/forgot-password", json={"email": "jane@example.com"})
    for token in (outbox["reset"][0][1], outbox["verify"][0][1]):
        r = await client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
