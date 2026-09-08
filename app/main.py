"""FastAPI application entry point: app wiring + server-rendered page routes.

The JSON API lives in the routers (``/api/posts``, ``/api/users``); this
module adds the Jinja2 page routes and the dual HTML/JSON exception handling.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import HTTPException as FastapiHttpException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import models
from app.config import settings
from app.database import database_engine, get_db_session
from app.health import router as health_router
from app.logging_setup import setup_logging
from app.middleware import (
    CSRFProtectionMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.routers import posts as posts_router
from app.routers import users as users_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(settings.log_level)
    yield
    await database_engine.dispose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts, www_redirect=False
)

template = Jinja2Templates(directory=Path(__file__).parent / "templates")

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

app.include_router(posts_router.router, prefix="/api/posts", tags=["Posts"])
app.include_router(users_router.router, prefix="/api/users", tags=["Users"])
app.include_router(health_router)


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
async def posts_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    total_post_count_query = await db.execute(
        select(func.count()).select_from(models.Post)
    )
    total_post_count = total_post_count_query.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .order_by(models.Post.date_posted.desc())
        .limit(settings.posts_per_page)
    )
    posts = result.scalars().all()

    has_more = len(posts) < total_post_count

    return template.TemplateResponse(
        request,
        "home_finished.html",
        {
            "posts": posts,
            "title": "Home",
            "limit": settings.posts_per_page,
            "has_more": has_more,
        },
    )


@app.get("/posts/{post_id}", include_in_schema=False, name="post_page")
async def post_page(
    request: Request,
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    post = result.scalars().first()

    if not post:
        raise FastapiHttpException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    return template.TemplateResponse(
        request, "post_finished.html", {"post": post, "title": post.title}
    )


@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def get_user_posts_page(
    request: Request,
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise FastapiHttpException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    count_result = await db.execute(
        select(func.count()).select_from(models.Post).where(models.Post.user_id == user_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == existing_user.id)
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit)
    )
    posts = result.scalars().all()

    has_more = (skip + len(posts)) < total

    return template.TemplateResponse(
        request,
        "users_posts_finished.html",
        {
            "posts": posts,
            "user": existing_user,
            "title": f"{existing_user.username} posts",
            "limit": settings.posts_per_page,
            "has_more": has_more,
        },
    )


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return template.TemplateResponse(request, "login.html", {"title": "Login"})


@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return template.TemplateResponse(request, "register.html", {"title": "Register"})


@app.get("/account", include_in_schema=False)
async def account_page(request: Request):
    return template.TemplateResponse(
        request, "account_finished.html", {"title": "Account"}
    )


@app.get("/forgot-password", include_in_schema=False)
async def forgot_password_page(request: Request):
    return template.TemplateResponse(
        request, "forgot_password.html", {"title": "Forgot Password"}
    )


@app.get("/reset-password", include_in_schema=False)
async def reset_password_page(request: Request):
    response = template.TemplateResponse(
        request, "reset_password.html", {"title": "Reset Password"}
    )
    # Keep the reset token (a query parameter) out of the Referer header
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(StarletteHttpException)
async def general_http_exception_handler(
    request: Request, exception: StarletteHttpException
):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception)

    message = (
        exception.detail
        if exception.detail
        else "An error occurred. Please check your request and try again."
    )

    return template.TemplateResponse(
        request,
        "error_finished.html",
        {
            "status_code": exception.status_code,
            "message": message,
            "title": exception.status_code,
        },
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exception: RequestValidationError
):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)

    return template.TemplateResponse(
        request,
        "error_finished.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again",
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )