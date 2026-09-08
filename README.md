# FastAPI Blog

An async FastAPI blog (built from the Corey Schafer tutorial series) hardened
into a production-ready app: httpOnly-cookie JWT auth with CSRF protection,
private S3 profile pictures served through short-lived pre-signed URLs, and a
full Docker deployment.

## Stack

- Python 3.13, FastAPI, uvicorn
- SQLAlchemy 2 (async) + Alembic migrations, PostgreSQL
- JWT auth (PyJWT) as an httpOnly `SameSite=Lax` cookie + custom-header CSRF
- S3 / moto (`AWS_ENDPOINT_URL`) for profile pictures via boto3
- Pillow (image processing), aiosmtplib (password-reset emails)
- Ratelimit: in-memory sliding window on login / password-reset endpoints
- Docker + GitHub Actions CI

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"

copy .env.example .env            # then fill in real values
```

Create the databases (`fastapi_blog` for the app, `test_blog` for pytest) on
your local PostgreSQL, then:

```bash
alembic upgrade head
uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

`AWS_ENDPOINT_URL=http://127.0.0.1:5000` in `.env` points boto3 at a local moto
server; run `moto_server` in another terminal for profile-picture uploads.

## Tests

Requires a local PostgreSQL with a `test_blog` database (default URL:
`postgresql+asyncpg://postgres:postgres@127.0.0.1/test_blog`):

```bash
pytest -q
```

## Docker deployment

```bash
docker compose up -d --build
```

- `db`: PostgreSQL 17, data in the `postgres_data` volume, `pg_isready` healthcheck.
- `app`: built from the Dockerfile — installs the wheel, runs `alembic upgrade
  head` on start, then serves the app as a non-root user on `127.0.0.1:8000`.

Before deploying **set production values** in `.env` (real secrets, empty
`AWS_ENDPOINT_URL` for real S3) and put a TLS-terminating reverse proxy (Caddy /
nginx) in front with:

```text
SECRET_KEY=...                # JWT signing key
COOKIE_SECURE=true            # HTTPS cookies
ALLOWED_HOSTS=blog.example.com
AUTH_USERNAME_FIELD=email
```

### Architecture notes

- The in-memory rate limiter is per-process, so run exactly **one** uvicorn
  worker per instance (the Docker entrypoint does this). Scale out by running
  more containers; a shared limiter would need Redis.
- CI (GitHub Actions) runs lint + the full test suite against a Postgres
  service container, then builds the image and pushes to GHCR on `main`.

## Endpoints

| Method | Path                           | Purpose                           |
| ------ | ------------------------------ | --------------------------------- |
| POST   | `/api/users`                   | register                          |
| POST   | `/api/users/token`             | login (sets httpOnly cookie)      |
| POST   | `/api/users/logout`            | clear session cookie              |
| GET    | `/api/users/me`                | current user                      |
| PATCH  | `/api/users/{id}`              | update profile                    |
| PATCH  | `/api/users/{id}/picture`      | upload profile picture            |
| DELETE | `/api/users/{id}`              | delete account                    |
| GET    | `/api/posts?skip=0&limit=10`   | list posts (paginated)            |
| POST   | `/api/posts`                   | create post                       |
| GET    | `/api/posts/{id}`              | read one post                     |
| PATCH  | `/api/posts/{id}`              | edit post                         |
| DELETE | `/api/posts/{id}`              | delete post                       |
| GET    | `/health/live`                 | liveness (no dependencies)        |
| GET    | `/health`                      | readiness (checks PostgreSQL)     |

Cookie-authenticated mutating requests must send `X-CSRF-Protected: 1`
(`auth.js` does this automatically). Bearer-token calls skip the CSRF check —
the documented path for API/script clients.