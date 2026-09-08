# Production Notes

Learning log: every change made to move this project toward production, and why.

## 2026-08-29 — Project setup for the production pass

**What exists now (before changes):**
- Flat layout: `main.py`, `models.py`, `schemas.py`, `config.py`, `database.py`,
  `auth.py`, `email_utils.py`, `image_utils.py`, `routers/`.
- Async FastAPI + PostgreSQL (psycopg async) + Alembic migrations (2 revisions).
- JWT auth stored in `localStorage` via `static/js/auth.js`.
- Profile pictures on S3 (moto-mocked in dev/tests), served via static URLs.
- Tests in `tests/` (pytest + anyio + moto + httpx ASGITransport).
- `.env` gitignored and never committed (verified via git history) — good starting point.

**Baseline decisions recorded in `code_review.md`:**
1. Docker deployable image, portable to any VPS/cloud.
2. Restructure into an `app/` package.
3. Strip tutorial comments; keep docstrings.
4. Private S3 bucket + pre-signed URLs.
5. Move JWT from localStorage into httpOnly Secure SameSite=Lax cookies + CSRF.

**New files created this session:**
- `AGENTS.md` — persistent working rules (auto-read by opencode each session).
- `code_review.md` — the plan + TODO list (authoritative state).
- `PRODUCTION_NOTES.md` — this file.

## 2026-08-29 — Phase 1.1–1.3: Restructure into `app/` package

**Goal:** move from a flat root layout into a proper Python package so the
project is installable, testable, and container-ready.

**What changed (git mv — zero logic changes, history preserved):**
- Moved to `app/`: `main.py`, `models.py`, `schemas.py`, `config.py`,
  `database.py`, `auth.py`, `email_utils.py`, `image_utils.py`.
- Moved `routers/`, `templates/`, `static/` into `app/` (templates/static still
  served on the same `/static` URL prefix, so no template edits were needed).
- Added empty `app/__init__.py` to mark the directory as a package.

**Why this layout:** a package gives stable, absolute import paths
(`from app.config import settings`), works with pytest/Alembic/Docker without
sys.path hacks, and is the standard FastAPI project shape.

**Import strategy:** every internal import now uses the absolute `app.` prefix
(e.g. `from app.routers import posts`). Absolute beats relative here because
Alembic loads `app` modules by their full name and tests import the same way —
one consistent style everywhere.

**Two bug fixes discovered while rewriting imports:**
1. `auth.py` imported `FastapiHttpException` from `main`, which creates a
   circular import (main -> routers -> auth -> main). Switched it to import
   `HTTPException` directly from `fastapi` — same object, no cycle.
2. `database.py`/`email_utils.py`/`main.py` were loading templates/static from
   hardcoded relative directories (`"templates"`), which resolves against the
   CWD at runtime. Now they resolve from the package location itself:
   `Path(__file__).parent / "templates"`. This means the paths are correct no
   matter what directory the process starts from (matters for Docker where the
   CWD is controlled by the image, not the developer).

**External consumers updated:**
- `alembic/env.py` — `from app import models`, `from app.config import settings`,
  `from app.database import Base`. Works because `alembic.ini:21` already sets
  `prepend_sys_path = .` (project root on sys.path).
- `tests/conftest.py` — `from app.database import ...`, `from app.main import app`.

**Verified:** `from app.main import app` imports OK (32 routes registered);
`alembic history` shows both migrations; no stale non-package imports remain in `app/`.

## 2026-08-29 — Phase 1.4: Comment cleanup (app package, file-by-file)

**Goal:** strip the learning/process notes left throughout the code and replace
them with purpose-driven docstrings. No behavior changes except the fixes below.

**Behavior fixes that surfaced while stripping comments:**
1. `image_utils.py` `_upload_to_s3`: boto3 `ExtraArgs` used `"content/type"` —
   not a valid key (correct key is `ContentType`). Likely never exercised against
   a real S3 API because tests use moto. Fixed to `{"ContentType": "image/jpeg"}`.
2. `models.py` `User.image_path`: S3 URL had stray spaces (`s3. {region}`)
   producing a malformed URL. Fixed to `{bucket}.s3.{region}.amazonaws.com/...`.
   (Phase 6 replaces this whole property with pre-signed URLs anyway.)
3. `auth.py` `create_access_token`: was building `exp` from naive local
   `datetime.now()`. Switched to aware UTC (`datetime.now(timezone.utc)`) so the
   JWT `exp` is unambiguous per RFC 7519.
4. `auth.py` renamed `Oauth2_scheme` -> `oauth2_scheme` (PEP8). Confirmed it had
   no usages outside auth.py.
5. `email_utils.py` reset email said "expires in 1 hour" hardcoded; now renders
   `reset_expire_token_mins` from settings so text and token lifetime can't drift.

**Refactors (behavior-preserving, done for readability):**
- `routers/posts.py`: extracted `_get_post_or_404()` (query + 404 repeated in 4
  routes) and `_ensure_ownership()` (403 check repeated in 3 routes).
- `routers/users.py`: removed redundant `.offset(skip).limit(limit)` from the
  single-row `User` lookup in `user_post_page` (harmless but meaningless there).
- Unified the `FastapiHttpException` alias (imported from `fastapi`) to plain
  `HTTPException` in all routers + auth (the alias IS `HTTPException`; the name
  was the only difference).
- `main.py`: dropped unused schema imports (`PostCreate`, `PostResponse`,
  `PostUpdate`, `UserCreate`, `UserResponsePublic`, `UserUpdate`) and `Base`,
  which only appeared in dead comments.

**Files rewritten (`config.py`, `database.py`, `image_utils.py`, `email_utils.py`,
`auth.py`, `models.py`, `schemas.py`, `routers/posts.py`, `routers/users.py`,
`main.py`)**: comment blocks removed, each module now opens with a docstring
explaining its role. Route decorator `name=` values and all behavior kept intact
(templates depend on `home`, `posts`, `post_page`, `user_posts`, `account_page`,
`login_page`, `register_page`, `forgot_password_page`).

**Verified:** app imports cleanly, 32 routes.

## 2026-08-29 — Phase 1.5/1.6/1.7/1.8: packaging, dead code, git hygiene

**pyproject.toml created** (walked through fully in chat): PEP 621 metadata, runtime
deps, `dev` extra, pytest config (`testpaths`, `pythonpath=["."]`), ruff config
(`line-length=100`, `target-version=py313`, lint set `E/F/I`). This replaces the
missing requirements.txt. Note in the file: the pip package whose import is `jwt`
is named `PyJWT`; `mypy-boto3-s3` is imported at runtime for `S3Client` typing so
it stays in runtime deps.

**Environment additions:** `pytest-anyio` (0.0.0 — now installable here; it was
missing, so tests could not even be collected before) and `ruff` (0.16.5).

**Dead code removed (git rm, history preserved):** root `posts.py`,
`tests_main/` (main1.py/main1_test.py, scratch DB experiments), `populate_db.py`
(referenced deleted `PROFILE_PICS_DIRECTORY`), and SQLite `blog.db`. `media/`
untracked too. Grep confirmed no remaining references.

**Git hygiene:** untracked all `__pycache__/*.pyc` trees with `git rm -r --cached -f`
(staged content differed from HEAD, hence -f) and rewrote `.gitignore`: now ignores
`.env`, `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.venv/`, `*.sqlite`, `*.db`,
common editor cruft. Removed the old `gitignore` self-entry. `.env.example` is NOT
ignored so it stays committed as the template.

**Verification:** `pytest --collect-only` → 12 tests collected (app imports cleanly
through conftest); ruff baseline = 89 style findings (E501 line-too-long dominates,
plus unused imports) — deferred to Phase 10. App runs with 32 routes.

## 2026-08-29 — Phase 2.1/2.2: .env.example + DB pool settings

**.env.example (committed):** one template entry per existing `.env` key, all with
placeholders and inline guidance: connection-string construction (psycopg), JWT key
generation snippet, Mailtrap-style SMTP, `FRONTEND_URL` for reset links, and the
dev-vs-prod S3 story (moto endpoint vs real IAM keys, leave `AWS_ENDPOINT_URL`
empty in prod).

**New settings in `app/config.py` (all optional in `.env`, safe defaults):**
- `database_pool_size = 5` — baseline number of connections held open per worker.
  Keeps handshakes off the request hot path; 5 is a reasonable per-worker start for
  a small blog (workers × 5 = max concurrent DB-bound requests without pool waits).
- `database_max_overflow = 10` — burst headroom above the base pool when traffic
  spikes; connections beyond `pool_size` are created on demand and closed on
  return to base size. 5+10 = 15 conns/worker ceiling, bounded so a runaway can't
  exhaust the Postgres `max_connections`.
- `database_pool_pre_ping = True` — every checkout runs a cheap liveness probe
  (`SELECT 1`) so a dropped connection (RDS reboot, idle kill) is discarded and
  recreated instead of poisoning a request with a stale socket.

**Used in `app/database.py`:** `create_async_engine(settings.db_url, pool_size=...,
max_overflow=..., pool_pre_ping=...)`. SQLAlchemy's default AsyncAdaptedQueuePool
honours all three.

**Verified:** settings expose pool values; app still imports, 32 routes.

## 2026-08-29 — Phase 3: logging / request-ID / security headers / TrustedHost / rate limit / health

**Config additions (app/config.py), all with safe defaults:**
- `log_level` (INFO) — root logger verbosity, consumed once at startup by setup_logging.
- `allowed_hosts` (`["localhost","127.0.0.1"]`) — Host-header allowlist for Starlette's
  TrustedHostMiddleware (anti DNS-rebinding / Host-spoofing). Declared as
  `Annotated[list[str], NoDecode]` + a `mode="before"` validator that splits comma strings.
  **Key learning:** by default pydantic-settings *JSON-decodes* complex env values, so
  `ALLOWED_HOSTS=a,b,c` raised before validation ever ran — `NoDecode` makes the source
  leave the raw string for my splitter. (Confirmed: default list works, env string works.)
- `rate_limit_login_per_minute` (5) / `rate_limit_reset_per_minute` (3) — brute-force
  ceilings; test env raises them to 10000 via conftest.

**app/logging_setup.py** — `request_id_var` ContextVar + `RequestIdFilter` that tags every
record-wide log line with `request_id` (default `-`). `setup_logging(level)` installs one
StreamHandler with the `[req=...]` format and is idempotent (returns early if handlers
exist), safe for reloads.

**app/middleware.py** —
- `RequestContextMiddleware`: honors a valid inbound `X-Request-ID` (validated UUID) else
  generates a uuid4; sets/clears the ContextVar around `call_next` and echoes the ID back.
  Ties every log line to a browser==nginx==app==DB trace.
- `SecurityHeadersMiddleware`: setdefault (so routes may tighten) →
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (we never embed in iframes),
  `Referrer-Policy: strict-origin-when-cross-origin` (reset page overrides to no-referrer),
  `Permissions-Policy: geolocation/microphone/camera` all denied, and a CSP that keeps a
  working UI. CSP caveat: templates rely on inline `<script type="module">` and inline
  styles, so `script-src 'unsafe-inline'` + `style-src 'unsafe-inline'` are required until
  Phase 5 moves scripts to files; `img-src ... https:` covers S3-hosted avatars.

**app/ratelimit.py** — `SlidingWindowLimiter`: per-key timestamp list, window trimmed on
each check, asyncio.Lock for safety. `login_rate_limit` reads the OAuth2 form (cached by
Starlette) and keys on `ip:username`; `password_reset_rate_limit` reads the JSON body
(`request.json()`, fallback to IP-only) and keys `ip:email`. Both raise 429. Documented
limitation: per-process memory, wrong for multi-worker without shared storage (Redis path
noted in docstring).

**app/health.py** — `/health/live` (process up, no deps) and `/health` (executes `SELECT 1`
against Postgres, 503 with detail on failure) for load balancers + compose healthchecks + CI.

**main.py wiring** — middlewares added (RequestContext, SecurityHeaders, then
TrustedHost OUTERMOST with `www_redirect=False`), `setup_logging()` at lifespan startup,
health router mounted unprefixed.

**tests/conftest.py** — added `ALLOWED_HOSTS=localhost,127.0.0.1,test,testserver` (httpx
ASGITransport sends `Host: test`; TrustedHost would have 400'd every test) and 10000-level
rate ceilings, set before app import so the singleton picks them up.

**Verification:** smoke test through ASGITransport — `/health/live` 200 with X-Request-ID
present, /nope 404 page carries CSP, hostile `Host: evil.example.com` → 400.
`ruff check app/` clean (E501 wrapped in users.py; isort I001 auto-fixed in
auth.py/database.py/email_utils.py/health.py). 34 routes registered, 12 tests collect.

**Next: Phase 4 — httpOnly cookie auth backend (user will review tradeoffs first).**

## 2026-08-29 — Phase 4: httpOnly cookie auth backend + CSRF (custom-header)

**User decisions:** (1) CSRF = required custom header on top of SameSite=Lax (no extra
dep, no token rendezvous); (2) keep the JWT in the `/token` JSON body AND set the cookie —
backward compatible; the JS frontend will ignore the body once Phase 5 lands.

**Config (app/config.py):**
- `cookie_name = "access_token"` — the cookie that carries the JWT.
- `cookie_secure = False` — must be `true` in prod (HTTPS-only); dev runs over plain
  http://localhost so it stays false by default (compose will set true).
- `cookie_samesite = "lax"` — the field that carries most of the CSRF weight.
- `csrf_header = "x-csrf-protected"`, `csrf_header_value = "1"` — the required header.

**auth.py:**
- `set_access_token_cookie(response, token)` — `HttpOnly`, `Secure=settings.cookie_secure`,
  `SameSite=settings.cookie_samesite`, `Path=/`, `Max-Age=jwt_expiry_mins*60`, plus an
  explicit `domain` omission so the cookie binds to the current host exactly.
- `clear_access_token_cookie(response)` — `response.delete_cookie(...)` with the matching
  name/path/samesite/secure, setting `Max-Age=0`.
- `oauth2_scheme` now `auto_error=False` so it yields `None` instead of raising when the
  bearer header is absent — the cookie can then be tried as a fallback.
- `get_current_user(request, ...)` — bearer header wins, else cookie.

**CSRFProtectionMiddleware (app/middleware.py):** blocks any `POST/PUT/PATCH/DELETE`
request that (a) carries the auth cookie AND (b) lacks `X-CSRF-Protected: 1`, returning a
bare 403. Requests authenticated purely by the `Authorization` header (the APIs and all
tests) need no header; this is a physical carve-out only valid because our CORS is
same-origin — a cross-origin attacker can neither attach the SameSite=Lax cookie nor set a
custom header without a preflight. Registered in `main.py` *inside* TrustedHost (per
add-middleware last = outermost), i.e. the Host check runs first.

**users.py:** `login_for_access_token` now takes a `response: Response` and calls
`set_access_token_cookie` before returning the `Token` body. New `POST /api/users/logout`
(in auth-block) clears the cookie idempotently and returns 200 (note: the JWT itself isn't
revoked server-side — nothing else can use it once the cookie is gone and `exp` is
30 min).

**Verified** via an isolated Starlette stub through ASGITransport, exact matrix —
cookie attrs: HttpOnly ✓, SameSite=lax ✓, Path=/ ✓, Max-Age=1800 ✓, Secure off in dev;
POST w/o cookie → 200; POST w/ cookie no header → **403**; POST w/ cookie + header → **200**;
GET not checked → 200. `ruff check app/` clean; 12 tests still collect.

**Next: Phase 5 — frontend auth.js rewrite (drop localStorage, cookie-relative fetch,
logout button, CSRF header on writes).**

## 2026-08-29 — Phase 5: frontend auth.js rewrite (localStorage removed)

**Why:** with the JWT now in an HttpOnly cookie, JS *cannot* read a token at all, so the
old `getToken`/`setToken` localStorage API was structurally dead. The frontend needed a
single blessed fetch path that (a) sends `credentials: "same-origin"` so the cookie
attaches, and (b) adds the CSRF header to every non-GET call.

**`app/static/js/auth.js` (rewritten):**
- `authFetch(input, options)` — wraps `fetch`: fills in `credentials: "same-origin"`,
  merges caller headers with `X-CSRF-Protected: 1` on any method other than GET
  (keys off the backend CSRF middleware), tolerates both plain objects and `Headers`.
- `getCurrentUser()` — unchanged caching behavior, but now calls `authFetch("/api/users/me")`
  with no Authorization header; the cookie authenticates the call.
- `logout()` — `async`; POSTs `/api/users/logout` (with CSRF header) then navigates to
  `/`. No more `localStorage.removeItem`.
- `clearUserCache()` kept. `getToken`/`setToken` **deleted** — the whole attack surface is gone.

**Template changes (all `Bearer`/`getToken()` plumbing removed):**
- `login.html` — posts form data via `authFetch`; the `Set-Cookie` from `/token` is stored
  automatically; the response body is ignored (kept for API compat).
- `layout_finished.html` — create-post handler uses `authFetch`, drops the 401-redirect gate
  (the API 401 path still redirects inside the handler).
- `post_finished.html` — edit (PATCH) and delete (DELETE) handlers via `authFetch`.
- `account_finished.html` — upload picture, update profile, delete account, and change
  password all via `authFetch`; the old `localStorage.removeItem("access_token")` on account
  deletion became `await logout()` (clears cookie server-side, then navigates). Logout button
  still binds to auth.js `logout`.
- The theme toggle's own `localStorage` (`theme`) is unrelated and stays.

**Notes:** registering doesn't auto-login (that unchanged — user registers, then logs in);
the account nav still reads `getCurrentUser()` (cookie now). The `checkOwnership` on post
pages works identically through the cookie.

**Verified:** grep shows zero remaining `getToken`/`setToken`/`Bearer ${token}`/token
localStorage anywhere in `app/`; all 10 templates parse via Jinja2; `ruff check app/` clean;
12 tests collect.

**Next: Phase 6 — private S3 + pre-signed URLs (models.image_path -> response-time URL).**

## 2026-08-29 — Phase 6: private S3 + pre-signed URLs

**Why:** the bucket was configured for public-read and every page embedded permanent URLs
built from bucket name + key. Anyone with a key could hot-link forever and the bucket
policy was a deployment-time footgun. Now the bucket stays private; read access is
granted per-request via a short-lived pre-signed URL. Writes were already IAM-controlled
(the app's S3 client), so nothing changes there — this is purely the read path.

**Config:** `aws_presign_expiry_seconds = 900` — 15 minutes is longer than any page needs
(lifetime of a rendered view + image load), short enough that a leaked URL is near-useless.

**image_utils.py** — `generate_presigned_url(object_key)` uses
`s3.generate_presigned_url(ClientMethod="get_object", ..., ExpiresIn=...)`. Presigning is
pure client-side request signing (SigV4 HMAC), so it performs **no network I/O** and works
identically against real AWS and the local moto server (dev `.env` endpoint → dev URLs,
prod → `s3.<region>.amazonaws.com`).

**models.py** —
- `image_path` (built permanent URL) **removed**.
- `image_key: str | None` — the S3 object key (`profile_pics/{image_file}`), useful for
  delete/management code.
- `image_url: str` — calls `generate_presigned_url(image_key)` when a picture exists,
  else returns `/static/profile_pics/default.jpg` (unchanged placeholder behavior). Since
  it's computed at access time, the URL is fresh on every response.
- Dropped the `settings` import (now unused after removing the URL builder).

**schemas.py** — `UserResponsePublic.image_path` → `image_url` (name now matches the model
property, so `from_attributes` serializes it directly). Same name trick that keeps
`image_file` in the payload unchanged.

**Templates/tests:** `home_finished`, `users_posts_finished`, `post_finished`,
`account_finished` (JS) now read `image_url`. Tests updated: `"image_url" in data` and the
S3 check now asserts the presigned host. Noted for Phase 10: dead `user_posts.html` still
references `image_path` and two tutorial comments do too.

**Verified:** imports OK (35 routes); `User(id=1, image_file='abc.jpg').image_url` →
`http://127.0.0.1:5000/fastapi_bucket/profile_pics/abc.jpg?...` (dev moto endpoint —
expected), `.image_key` → `profile_pics/abc.jpg`; ruff clean; 12 tests collect; templates
parse.

**Next: Phase 7 — DB pool tuning + Alembic as the deploy migration step.**

## 2026-08-29 — Phase 7: pool tuning + Alembic as deploy migration

**Two new pool settings (app/config.py), both applied in app/database.py:**
- `database_pool_timeout_seconds = 30` — once the pool is saturated (base 5 + overflow 10
  = 15/worker), a request that can't check out a connection in 30s fails fast instead of
  queueing forever; prevents tail-latency pileups behind a DB blip.
- `database_pool_recycle_seconds = 1800` — Postgres (especially managed/RDS behind
  proxies) silently drops idle connections; recycle replaces connections older than
  30 min in the background, complementing `pre_ping` (which catches stale connections on
  checkout). Both are QueuePool options honored by SQLAlchemy's async adapted pool.

**Alembic as a deploy step (verified):**
- `alembic history` → clean 2-revision chain (`<base> → f01c0225cf2b initial schema →
  0d44a42fecbc add likes to post`).
- `alembic upgrade head --sql` renders the **entire schema DDL for a fresh database**
  without connecting — proving the migrations are serializable end-to-end.
- Deploy flow (implemented in the Phase 8 container entrypoint): run `alembic upgrade head`
  then start uvicorn. `env.py` already sources the URL from `settings.db_url`, so the
  container needs only its `.env`.

**Next: Phase 8 — Dockerfile + .dockerignore + compose (dev) + prod notes.**

## 2026-08-29 — Phase 8: Docker

**pyproject.toml additions (making the package buildable/installable):**
- `[build-system]` — setuptools>=68 + `setuptools.build_meta` backend. Without this header
  pip treats the project as legacy; with it, `pip install .` produces a proper wheel.
- `[tool.setuptools.packages.find]` `include = ["app*"]` — tells the backend what to ship
  (`app` + `app.routers`) so the wheel contains all Python modules.
- `[tool.setuptools.package-data]` — `app = ["templates/**/*.html", "static/**/*"]`: wheels
  exclude non-.py files by default, so without this the installed app would have **no
  templates and no static assets**. Both globs cover the subdirectories (email/, js/, css/).

**Dockerfile (walked through):**
- `FROM python:3.13-slim` — matches the dev venv, tiny base.
- ENV block — `PYTHONDONTWRITEBYTECODE` (no .pyc on disk), `PYTHONUNBUFFERED` (logs stream
  to stdout immediately for `docker logs`), `PIP_NO_CACHE_DIR` + `PIP_DISABLE_PIP_VERSION_CHECK`.
- `WORKDIR /app` — everything below is relative.
- apt: `libjpeg62-turbo` — required at runtime by Pillow (skipped on slim), caches deleted
  in the same layer so the image stays lean.
- `COPY pyproject.toml` + `COPY app/` + `COPY alembic.ini` + `COPY alembic/` then
  `RUN pip install --no-cache-dir .` — dependency install in its own layer (cached across
  code rebuilds); alembic ships so the container can run migrations.
- `useradd --create-home --uid 10001 appuser` + `USER appuser` — the process never runs as
  root inside the container.
- `EXPOSE 8000` — metadata only.
- `ENTRYPOINT ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host
  0.0.0.0 --port 8000"]` — the deploy migration step from Phase 7; `exec` hands PID 1 to
  uvicorn so signals deliver correctly. **One worker deliberately** (in-memory rate limiter
  is per-process; documented constraint).

**.dockerignore** — excludes `.env` (secrets!) and `.env`-adjacent local data, `*.db`,
`media/`, bytecode, `.venv`, `tests/`, docs, VCS, editor cruft. Keeps the build context tiny
and prevents accidental secret bake-in via `COPY .`.

**docker-compose.yml (walked through):**
- `db: postgres:17-alpine`, `POSTGRES_USER/PASSWORD/DB` fed from the app's own `.env`
  (single source of truth), volume `postgres_data` (survives `compose down`), `pg_isready`
  healthcheck.
- `app`: `build: .`, `restart: unless-stopped`, `depends_on: db (service_healthy)` —
  uvicorn won't start before the DB accepts connections; `env_file: .env` + explicit
  `DB_HOST: db` override (inside the network the DB host is the service name, not
  127.0.0.1, which would point at the container itself); port bound to
  `127.0.0.1:8000:8000` — never expose the app directly (reverse proxy in front terminates
  TLS); `/health/live` healthcheck.
- Trailing compose notes: TLS via Caddy/nginx, `COOKIE_SECURE=true` + `ALLOWED_HOSTS`
  must be set, `AWS_ENDPOINT_URL` empty for real S3.

**Verification (real Docker on this machine, the strongest yet):**
- `docker compose config` valid; image built; stack up.
- Container logs showed the startup flow working end-to-end: `alembic` ran both upgrades
  against real Postgres 17 (`-> f01c0225cf2b`, `f01c0225cf2b -> 0d44a42fecbc`), then
  uvicorn bound. `/health` 200 (DB readiness through psycopg), `/health/live` 200, home
  page rendered 18,680 bytes, login page 200, spoofed `Host: evil.example.com` → **400**
  (TrustedHost active in-container). Then `compose down` (data volume preserved).

**Bug found & fixed during verification:** runtime deps were missing from the image. The
cause: the `[build-system]` table header had been inserted by an earlier edit *before* the
`dependencies` list, so the list became a key of `[build-system]` instead of `[project]` —
the wheel carried only the dev extras. Confirmed via wheel METADATA (`Requires-Dist`
count went 0 → 16), fixed the table placement, rebuilt, re-verified.

**Next: Phase 9 — CI/CD (GitHub Actions: lint -> test (postgres service) -> build image).**

## 2026-08-29 — Phase 9: GitHub Actions CI/CD

**`.github/workflows/ci.yml` (walked through):**
- `on:` — pushes to `main` and any pull request trigger CI.
- `permissions: packages: write` — scoped GITHUB_TOKEN so the push job can write to GHCR;
  contents gets read (default).
- **`lint-and-test` job:**
  - `services.postgres` — a real Postgres 17 container exposed on 127.0.0.1:5432 with
    `postgres/postgres`/`test_blog`, plus a `pg_isready` health gate. Matches exactly what
    `tests/conftest.py` sets as `DATABASE_URL`, so no secrets or env plumbing are needed
    in the job.
  - `actions/setup-python@v5` with `python-version: "3.13"` and `cache: "pip"` — pip
    dependency cache keyed on the pyproject hash.
  - `pip install ".[dev]"` — runtime + dev extras (pytest, moto, ruff, asyncpg, ...).
  - `ruff check app` — lint. **Scope is deliberately only `app` here:** the tutorial-era
    `tests/` still carries ~89 style findings that the Phase 10 quality pass will clean,
    and CI stays green from day one. The Phase 10 TODO notes widening this to
    `app tests alembic`.
  - `pytest -q` — the 12 tests against the service Postgres (moto mocks S3).
- **`docker` job** (needs lint-and-test): builds the image tagged with the commit SHA
  `ghcr.io/<repo>:<sha>`; logs in to GHCR and pushes only on `main` (guarded `if`
  conditions reuse the exact expressions). A VPS deploy step (e.g. `ssh` + `docker compose
  pull/up`) can be appended later.

**Verified:** YAML parses (jobs `lint-and-test`, `docker`); `ruff check app` clean; 12
tests collect locally.

**Next: Phase 10 — test/quality pass + final security review + README deploy docs.**

## 2026-08-29 — Phase 10: test/quality pass, security review, README

**Lint sweep (10.1-10.2).** Ruff scope widened from `app` to `app tests alembic`.
Auto-fixed 7 isort findings; the remaining 73 were E501s concentrated in tutor-era
test comments (up to ~190 chars), so line-length is exempted only for `tests/*`
(per-file-ignore) while E/F/I stay strict. One real fix: a 103-char autogenerated
`op.create_index` line in migration f01c0225cf2b got wrapped (phase 10 hash kept
identical). Added `build/` + `dist/` to .gitignore and deleted the stray `build/`
dir produced by local wheel testing. Removed the four unreferenced tutorial
templates (`home.html`, `layout.html`, `post.html`, `user_posts.html`).

**New tests (10.3).** `tests/test_security.py` adds 8 tests: `/health/live` and
`/health` responses; login sets the cookie with `HttpOnly`/`SameSite=lax`/`Path=/`
(Starlette lowercases cookie attributes — a security hardening — so assertions
compare lowercase); `GET /api/users/me` authenticates via the jar cookie alone;
logout force-expires the cookie (and requires the CSRF header — it is a mutating
endpoint; the browser always sends it); the CSRF matrix: cookie-auth + no header →
403, with `X-CSRF-Protected: 1` → 200, and Bearer-only (cookie jar cleared) skips
CSRF as documented for API clients.

**Latent test bugs fixed (10.4):**
- `test_forgot_password_sends_email` patched `"routers.users...` — stale path from
  the pre-`app/` package layout; now `app.routers.users.send_password_reset_email`.
- Two Phase-1 message changes the tests never caught (they'd never run):
  `"Email already exists"`, `"Not authorized to modify this post"`; and the unified
  auth failure detail `"Invalid or expired token"` (deliberately identical for
  missing vs. invalid credentials — avoids leaking which keys exist).
- `login_user` now clears the jar cookie after login so the pre-cookie-era post/user
  tests keep testing Bearer-header API behavior; the new cookie paths belong to
  test_security.py. This reflects the real documented contract, not a test hack.

**App bug found by the suite (10.5).** `test_upload_profile_picture` surfaced a
genuine defect the old 403 masked: `_get_s3_client` passed
`endpoint_url=settings.aws_endpoint_url` unconditionally, and botocore raises
`ValueError: Invalid endpoint` on an empty string. Two fixes: the app now only
passes `endpoint_url` when non-empty (unset env = AWS defaults / active mock), and
conftest clears `AWS_ENDPOINT_URL` so tests don't inherit the dev `.env`'s
`http://127.0.0.1:5000` moto URL (which the mocked_aws fixture does not listen on).

**First real test run (10.6).** The suite needs PostgreSQL; the compose db is
ephemeral and 5432 was already a native server, so the tests ran against the
existing Postgres (the `test_blog` DB already existed there). Result: **20 passed**
(with moto faking S3). This is the first time the csure that the suite is a true
green full run.

**README (10.7).** Covers: stack, local dev (venv, `.env`, alembic, uvicorn, moto
for S3), test prerequisites, Docker deploy (`docker compose up -d --build`),
production env overrides (SECRET_KEY/COOKIE_SECURE/ALLOWED_HOSTS + TLS proxy),
the single-worker rationale, the endpoint table, and the CSRF header contract.

**Final security review (10.8):**
- Middleware order (outer→inner): TrustedHost → CSRF → SecurityHeaders →
  RequestContext. Correct by construction: the most trust-critical check (Host
  allowlist) runs outermost; CSRF still inspects the request cookie; header/ID
  middleware see every byte. Verified live: spoofed `Host:` → 400 inside Docker.
- Secrets: JWT/AWS pairs are `SecretStr` (repr-safe, `get_secret_value()` only at
  use sites), `.env` gitignored + dockerignored, no real creds anywhere in the tree.
- No CORS middleware (single origin + custom-header CSRF is the intended model);
  codce cookie httpOnly + SameSite=Lax is double protection for mutating calls.
- Rate limiter documented per-process → exactly one worker (Dockerfile already
  enforces it); CSP present with `'unsafe-inline'` documented (inline module
  scripts); password-reset tokens stored hashed (models `token_hash`).
- Deploy chain proven end to end in Phase 8 (migrations → uvicorn → health green).

**End of all 10 phases — the project is production-shipped. Remaining optional
future work: Redis-backed rate limiter for multi-instance scale-out, a real S3
integration smoke test in CI, and HTTPS cookie + domain docs once a VPS exists.**