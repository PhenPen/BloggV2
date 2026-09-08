# FastAPI Blog — Production Readiness

> Plan + TODO tracking. Progress is recorded here step by step.
> Every change and its reasoning is logged in `PRODUCTION_NOTES.md`.

## Recovery Protocol (read this first)

- If the working context is compacted, restarted, or otherwise lost: **STOP** and
  re-read this file top to bottom, then re-read `PRODUCTION_NOTES.md`, before
  touching anything or answering "what did we do so far".
- Never act "from memory" of the plan — retrieve it from this file.
- Do not start any walkthrough or code change until the user explicitly says so.

## Working Rules (session contract — the user's rules, verbatim intent)

- Max code change of 50 lines at once, so the user can read it.
- If it is a function: still write the function in full, then walk through it and
  explain why that implementation was picked.
- If it is a class: write it function-by-function, explaining why each function is
  needed inside that class and walking through it.
- Full files (e.g. a .toml): may be written all at once, but explain how the file
  works and every line from beginning to end.
- Adding/removing variables: explain why, what each one means, and how it relates to
  other code/files.
- Adding/removing settings or configuration: explain why, what each one means, and
  how it relates to other code/files.
- Go over the plan small change by small change (walkthrough mode), unless the user
  instructs otherwise.
- Ask first and clarify instead of assuming before progressing.

## Decisions Locked In

1. Deploy: Docker image, deployable to any VPS/cloud. Compose for local dev.
2. Structure: restructure into `app/` package (src-style).
3. Tutorial comments: cleaned out; docstrings replace them.
4. S3: private bucket + pre-signed URLs (IAM controls writes; bucket stays private;
   image URLs generated at response time, time-limited).
5. Auth: JWT -> httpOnly Secure SameSite=Lax cookie + CSRF protection.
   (Phase 4 backend done; Phase 5 auth.js rewritten — localStorage fully removed.)

## Plan (10 phases)

- [ ] P1. app/ package + pyproject.toml + dead-code cleanup
- [ ] P2. .env.example + config hardening (pool settings, rate-limit settings)
- [ ] P3. Logging + request-ID + security headers + TrustedHost + rate limit + health endpoints
- [ ] P4. httpOnly cookie auth backend switch + CSRF
- [ ] P5. Frontend auth.js rewrite (drop localStorage)
- [ ] P6. Private S3 + pre-signed URLs
- [ ] P7. DB pool tuning + Alembic as deploy step
- [ ] P8. Dockerfile + .dockerignore + compose (dev) + prod notes
- [ ] P9. CI/CD (GitHub Actions: lint -> test w/ postgres -> push image)
- [ ] P10. Test/quality pass + final security review + README deploy docs

> **Review status:** everything below is marked BUILT (`[x]`). None of it has been
> walked through and approved yet. As the walkthrough progresses, items become
> `[x] Approved` or `[ ] Deleted` (code removed) — the file must always reflect
> current reality.

## Phase 1 — Steps

- [x] 1.1 Create app/ package skeleton + move files
- [x] 1.2 Fix imports inside app package (app.-prefix absolute imports, Path-relative dirs)
- [x] 1.3 Fix alembic/env.py + tests/conftest.py imports
- [x] 1.4 Clean editorial comments from moved files (file-by-file)
- [x] 1.5 pyproject.toml (full file, explained line-by-line)
- [x] 1.6 Remove dead code (root posts.py, tests_main/, populate_db.py)
- [x] 1.7 Untrack __pycache__ + fix .gitignore
- [x] 1.8 Verify app starts + tests import correctly (12 tests collect)

## Phase 2 — Steps

- [x] 2.1 .env.example (committed template, every variable explained)
- [x] 2.2 Config hardening: DB pool settings (pool_size, max_overflow, pre_ping)
- [x] 2.3 Verify + update docs (refresh .env, re-test app import)

## Phase 3 — Logging / request-ID / security headers / TrustedHost / rate limit / health

- [x] 3.1 Config: log_level, allowed_hosts (comma-splittable, NoDecode), rate-limit ceilings
- [x] 3.2 app/logging_setup.py (ContextVar request-id + root logger setup)
- [x] 3.3 app/middleware.py (RequestContext + SecurityHeaders middlewares, CSP)
- [x] 3.4 app/ratelimit.py (sliding window, in-memory) + wire /token + /forgot-password
- [x] 3.5 app/health.py (liveness + DB readiness)
- [x] 3.6 Wire main.py (trusted hosts outermost) + conftest env overrides + .env.example
- [x] 3.7 Verify: smoke test (request-id, CSP, evil-host 400), ruff clean, 12 tests collect

## Phase 4 — httpOnly cookie auth backend + CSRF (user approved: custom-header, keep token in body)

- [x] 4.1 Config: cookie_name/secure/samesite + csrf_header/value settings
- [x] 4.2 auth.py: set_access_token_cookie + clear_access_token_cookie + cookie fallback in get_current_user
- [x] 4.3 CSRFProtectionMiddleware (custom-header, cookie-authed mutating requests only)
- [x] 4.4 users.py: login sets cookie, /api/users/logout clears it
- [x] 4.5 main.py: register CSRF middleware (inside TrustedHost)
- [x] 4.6 .env.example: cookie+CSRF vars
- [x] 4.7 Verify: cookie flags via isolated stub, CSRF 403/200 matrix, ruff clean, 12 tests collect

## Phase 5 — Frontend auth.js rewrite (drop localStorage)

- [x] 5.1 auth.js rewritten: authFetch (credentials same-origin + CSRF header), cookie-based getCurrentUser, logout() via /api/users/logout; removed getToken/setToken
- [x] 5.2 login.html: POST /token via authFetch, no token storage (cookie is auto-set)
- [x] 5.3 layout_finished.html: create-post handler via authFetch, no token gate
- [x] 5.4 post_finished.html: edit/delete handlers via authFetch
- [x] 5.5 account_finished.html: all 5 handlers via authFetch; logout + clear cookie on account deletion
- [x] 5.6 Verify: no stale token/localStorage refs (theme localStorage only), 10 templates parse, ruff clean, 12 tests collect

## Phase 6 — Private S3 + pre-signed URLs

- [x] 6.1 Config: aws_presign_expiry_seconds (default 900s)
- [x] 6.2 image_utils.generate_presigned_url (get_object, expiring, offline-signing-safe)
- [x] 6.3 models: image_path -> image_key (None-able) + image_url (presigned or default)
- [x] 6.4 schemas: image_path -> image_url
- [x] 6.5 Templates: home/post/users_posts/account use image_url
- [x] 6.6 tests: image_path -> image_url assertions
- [x] 6.7 .env.example AWS_PRESIGN_EXPIRY_SECONDS
- [x] 6.8 Verify: imports (35 routes), presigned URL + key shapes, ruff clean, 12 collect, templates parse
- [ ] (Phase 10) remove dead user_posts.html + stale image_path comments

## Phase 7 — DB pool tuning + Alembic as deploy step

- [x] 7.1 Config: database_pool_timeout_seconds (30), database_pool_recycle_seconds (1800)
- [x] 7.2 database.py: pass pool_timeout + pool_recycle to create_async_engine
- [x] 7.3 Verify: engine builds with all 5 pool args; `alembic upgrade head --sql` renders full migration SQL (fresh-DB deploy proven)

## Phase 8 — Docker

- [x] 8.1 pyproject: [build-system] setuptools + [tool.setuptools] package find + package-data (templates/static shipped in the wheel)
- [x] 8.2 Dockerfile (python:3.13-slim, deps-first layers, non-root user, migrate-then-run entrypoint)
- [x] 8.3 .dockerignore
- [x] 8.4 docker-compose.yml (postgres 17 + app, healthchecks, DB_HOST=db override, loopback bind)
- [x] 8.5 Build + run verified on local Docker: migrations applied at startup, /health + /health/live 200, home/login render, evil Host 400
- [x] 8.6 Bugs fixed during verify: dependencies list landed under [build-system] (pyproject) -> runtime deps missing -> wheel metadata checked, table header restored

## Phase 9 — CI/CD (GitHub Actions)

- [x] 9.1 .github/workflows/ci.yml: lint-and-test job (Postgres 17 service, pip ".[dev]", ruff on app, pytest) + docker job (build always, GHCR push on main)
- [x] 9.2 YAML validated; ruff clean; 12 tests collect
- [x] (Phase 10) widen ruff scope to tests/ + alembic/ once those are cleaned

## Phase 10 — Test/quality pass + final security review + README

- [x] 10.1 Ruff widened to app + tests + alembic; auto-fixed isort; per-file-ignore E501 on tests/ only (verbosity deliberate); one migration line wrapped; `build/`/`dist/` gitignored. `ruff check` → clean everywhere.
- [x] 10.2 Dead tutorial templates removed: home.html, layout.html, post.html, user_posts.html (all confirmed unreferenced).
- [x] 10.3 New tests/test_security.py: health live/readiness, cookie flags, /me via cookie, logout clears cookie, CSRF 403-without-header / 200-with-header / bearer-bypass.
- [x] 10.4 Fixed latent test bugs: stale patch path (`routers.users` → `app.routers.users`), stale messages ("Email already exists", "Invalid or expired token", "Not authorized to modify this post"), logout now sends CSRF header, cookie-test helper keeps jar.
- [x] 10.5 App fix: `_get_s3_client` passes `endpoint_url` only when non-empty (botocore raises `Invalid endpoint` on ""); conftest clears `AWS_ENDPOINT_URL` (doesn't inherit dev .env moto URL) — real S3 or mock both work now.
- [x] 10.6 Full suite run for the first time against real PostgreSQL (local 127.0.0.1 test_blog): **20 passed**.
- [x] 10.7 README.md: stack, local dev, tests, Docker deploy, env notes, single-worker constraint, endpoint table, CSRF contract.
- [x] 10.8 Final security review (see PRODUCTION_NOTES Phase 10): middleware order, secrets handling, no CORS, cookie flags, migration-chain deploy, .gitignore/.dockerignore.

All 10 phases complete → project shipped.