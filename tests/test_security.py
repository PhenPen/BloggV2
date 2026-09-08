import pytest
from httpx import AsyncClient

from tests.conftest import create_test_user

CSRF_HEADER = "X-CSRF-Protected"


async def cookie_login(client: AsyncClient) -> str:
    """POST /token and leave the httpOnly cookie in the client jar."""
    response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "testpassword123"},
    )
    assert response.status_code == 200, f"cookie_login failed: {response.text}"
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_health_live(client: AsyncClient):
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_health_readiness(client: AsyncClient):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_login_sets_http_only_cookie(client: AsyncClient):
    await create_test_user(client)
    response = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "testpassword123"},
    )

    assert response.status_code == 200
    # The JSON body still returns the JWT (kept for legacy clients); the
    # production auth path is the httpOnly cookie below.
    assert "access_token" in response.json()

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/;" in set_cookie


@pytest.mark.anyio
async def test_get_me_works_via_cookie(client: AsyncClient):
    user = await create_test_user(client)
    await cookie_login(client)  # httpx's cookie jar stores the session cookie

    response = await client.get("/api/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


@pytest.mark.anyio
async def test_logout_clears_cookie(client: AsyncClient):
    await create_test_user(client)
    await cookie_login(client)

    response = await client.post("/api/users/logout", headers={CSRF_HEADER: "1"})
    # logout is a mutating cookie-authenticated endpoint, so it obeys CSRF
    # (the frontend always sends the header via authFetch).

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert set_cookie.startswith("access_token=")
    assert "max-age=0" in set_cookie


@pytest.mark.anyio
async def test_csrf_rejects_missing_header_on_cookie_auth(client: AsyncClient):
    user = await create_test_user(client)
    await cookie_login(client)  # now cookie-authenticated

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "no_csrf_header"},
    )

    assert response.status_code == 403
    assert "CSRF" in response.text


@pytest.mark.anyio
async def test_csrf_allows_request_with_header(client: AsyncClient):
    user = await create_test_user(client)
    await cookie_login(client)

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "csrf_ok"},
        headers={CSRF_HEADER: "1"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "csrf_ok"


@pytest.mark.anyio
async def test_csrf_not_required_with_bearer_header(client: AsyncClient):
    user = await create_test_user(client)
    token = await cookie_login(client)
    # Bearer-only auth (script/CLI clients) has no cookie jar to defend.
    client.cookies.clear()

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "bearer_ok"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "bearer_ok"