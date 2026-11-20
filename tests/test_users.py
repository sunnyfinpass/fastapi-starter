from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.users.models import Role
from app.modules.users.repository import UserRepository
from tests.conftest import bearer

API = "/api/v1"


async def _promote_to_admin(maker: async_sessionmaker[AsyncSession], email: str) -> None:
    async with maker() as session:
        repo = UserRepository(session)
        user = await repo.get_by_email(email)
        assert user is not None
        user.role = Role.admin
        await repo.save(user)


async def test_update_profile(client: AsyncClient, make_user) -> None:
    tokens = await make_user()
    r = await client.patch(f"{API}/users/me", headers=bearer(tokens), json={"full_name": "Jane Doe"})
    assert r.status_code == 200
    assert r.json()["full_name"] == "Jane Doe"


async def test_regular_user_cannot_list_users(client: AsyncClient, make_user) -> None:
    tokens = await make_user()
    r = await client.get(f"{API}/users", headers=bearer(tokens))
    assert r.status_code == 403


async def test_admin_can_list_and_manage_users(client: AsyncClient, make_user, maker) -> None:
    admin = await make_user("admin@example.com")
    await make_user("bob@example.com")
    await _promote_to_admin(maker, "admin@example.com")

    r = await client.get(f"{API}/users", headers=bearer(admin))
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 2
    bob_id = next(u["id"] for u in users if u["email"] == "bob@example.com")

    r = await client.patch(f"{API}/users/{bob_id}", headers=bearer(admin), json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # deactivated users can't log in
    r = await client.post(f"{API}/auth/login", data={"username": "bob@example.com", "password": "supersecret123"})
    assert r.status_code == 401
