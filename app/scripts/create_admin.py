"""Create (or promote) an admin:  uv run python -m app.scripts.create_admin you@example.com 'Passw0rd!'"""

import asyncio
import sys

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.modules.users.models import Role
from app.modules.users.repository import UserRepository


async def main(email: str, password: str) -> None:
    async with SessionLocal() as session:
        repo = UserRepository(session)
        user = await repo.get_by_email(email.lower())
        if user is None:
            user = await repo.create(email.lower(), hash_password(password), "Admin")
        user.role = Role.admin
        user.is_verified = True
        await repo.save(user)
        print(f"Admin ready: {user.email}")
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m app.scripts.create_admin EMAIL PASSWORD")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
