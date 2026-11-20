import os
from collections.abc import AsyncIterator, Awaitable, Callable

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "supersecret123"


@pytest.fixture
async def maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[tuple[str, str]]]:
    """Captures 'sent' emails instead of logging them."""
    box: dict[str, list[tuple[str, str]]] = {"reset": [], "verify": []}
    monkeypatch.setattr(
        "app.modules.auth.router.send_password_reset_email",
        lambda to, token: box["reset"].append((to, token)),
    )
    monkeypatch.setattr(
        "app.modules.auth.router.send_verification_email",
        lambda to, token: box["verify"].append((to, token)),
    )
    return box


@pytest.fixture
def make_user(client: AsyncClient) -> Callable[..., Awaitable[dict[str, str]]]:
    async def _make(email: str = "jane@example.com", password: str = PASSWORD) -> dict[str, str]:
        r = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
        assert r.status_code == 201, r.text
        r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert r.status_code == 200, r.text
        return r.json()

    return _make


def bearer(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
