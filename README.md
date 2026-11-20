# FastAPI Starter: full auth module (senior-style layout)

## Run it
```bash
# install uv once: https://docs.astral.sh/uv/
cp .env.example .env                                   # then set SECRET_KEY (openssl rand -hex 32)
uv sync                                                # creates .venv, installs deps
uv run alembic revision --autogenerate -m "init"       # generate first migration
uv run alembic upgrade head                            # create tables (SQLite file app.db)
uv run python -m app.scripts.create_admin admin@example.com 'ChangeMe123!'
uv run fastapi dev app/main.py                         # http://localhost:8000/docs
```
Swagger's green **Authorize** button works: log in with your email as `username`.
Reset/verification links are printed in the server console (see `app/core/email.py`).

## Everyday commands
```bash
uv run pytest                 # tests
uv run ruff check . --fix     # lint
uv run ruff format .          # format
uv run mypy app               # type check
uv run pre-commit install     # ruff on every commit
uv run alembic revision --autogenerate -m "add posts"   # after changing models
uv run alembic upgrade head
```

## Endpoints (all under /api/v1)
| Method | Path                      | Auth        | Purpose                                         |
|--------|---------------------------|-------------|-------------------------------------------------|
| POST   | /auth/register            | -           | Create account (sends verification email)       |
| POST   | /auth/login               | -           | Form: username(email)+password -> access+refresh|
| POST   | /auth/refresh             | -           | Rotate refresh token -> new token pair          |
| POST   | /auth/logout              | -           | Revoke one refresh token                        |
| POST   | /auth/logout-all          | Bearer      | Revoke every session of the user                |
| POST   | /auth/change-password     | Bearer      | Needs current password; signs out everywhere    |
| POST   | /auth/forgot-password     | -           | Always 202 (no user enumeration)                |
| POST   | /auth/reset-password      | -           | Token from email -> new password                |
| POST   | /auth/verify-email        | -           | Token from email                                |
| POST   | /auth/resend-verification | Bearer      | Resend verification email                       |
| GET    | /users/me                 | Bearer      | Current user                                    |
| PATCH  | /users/me                 | Bearer      | Update own profile                              |
| GET    | /users                    | Admin       | List users (skip, limit)                        |
| PATCH  | /users/{id}               | Admin       | Change role / activate / deactivate             |

## How the tokens work
- **Access token**: JWT, 15 min. Sent as `Authorization: Bearer <token>`.
- **Refresh token**: random opaque string, 7 days, stored **hashed** in `refresh_tokens`.
  Every refresh *rotates* it (old one is revoked). If a revoked token is replayed we assume
  theft and revoke all the user's sessions.
- **Reset / verify tokens**: short-lived JWTs with a `type` claim, so they can never be used
  as access tokens. Reset tokens are single-use (tied to the current password hash).
- Passwords: argon2 via `pwdlib`.

## Protecting your own endpoints
```python
from app.api.deps import AdminUser, CurrentUser, VerifiedUser, require_roles

@router.get("/mine")
async def mine(user: CurrentUser): ...               # any logged-in user

@router.post("/posts")
async def create_post(user: VerifiedUser): ...       # logged in + email verified

@router.delete("/posts/{id}")
async def delete_post(id: int, admin: AdminUser): ...# admin only

# custom roles: add to the Role enum, then
Editor = Annotated[User, Depends(require_roles(Role.admin, Role.editor))]
```

## Mental map
| You know (Laravel / NestJS)         | FastAPI here                                   |
|-------------------------------------|------------------------------------------------|
| Route file / Controller             | `modules/<name>/router.py`                     |
| FormRequest / DTO + class-validator | Pydantic schemas in `schemas.py`               |
| API Resource                        | `response_model=` + Pydantic schema            |
| Eloquent / TypeORM entity           | SQLAlchemy model in `models.py`                |
| Repository                          | `repository.py`                                |
| Service / provider                  | `service.py` + wiring in `api/deps.py`         |
| Guard / Gate / middleware           | `Depends(...)` (CurrentUser, require_roles)    |
| NestJS Module                       | a folder in `app/modules/`                     |
| config() / ConfigModule             | `pydantic-settings` in `core/config.py`        |
| Exception filter / Handler          | `core/exceptions.py`                           |
| PHPUnit / Jest                      | pytest + httpx AsyncClient                     |

## Rules of thumb
- Routers: HTTP only. Services: business rules (raise `AppError` subclasses). Repositories: DB only.
- Always declare `response_model` so you never leak fields like password hashes.
- `async def` only with async libraries; never call blocking code inside it.

## Before production
Rate-limit login/forgot-password (e.g. `slowapi`), send real email, restrict CORS origins,
use Postgres, and consider delivering the refresh token as an httpOnly cookie for browser apps.
