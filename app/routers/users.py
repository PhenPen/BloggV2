"""User, auth, and profile-picture routes mounted at ``/api/users``."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from botocore.exceptions import ClientError
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from PIL import UnidentifiedImageError
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app import models
from app.auth import (
    CurrentUser,
    clear_access_token_cookie,
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    set_access_token_cookie,
    verify_password,
)
from app.config import settings
from app.database import get_db_session
from app.email_utils import send_password_reset_email
from app.image_utils import (
    delete_profile_image,
    process_profile_image,
    upload_profile_image,
)
from app.ratelimit import login_rate_limit, password_reset_rate_limit
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    PaginatedPostResponse,
    PostResponse,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserResponsePrivate,
    UserResponsePublic,
    UserUpdate,
)

router = APIRouter()


@router.post("", response_model=UserResponsePrivate, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    result = await db_session.execute(
        select(models.User).where(func.lower(models.User.username) == user.username.lower())
    )
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    result = await db_session.execute(
        select(models.User).where(func.lower(models.User.email) == user.email.lower())
    )
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    new_user = models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash=hash_password(user.password),
    )
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)
    return new_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[None, Depends(login_rate_limit)],
):
    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == form_data.username.lower())
    )
    existing_user = result.scalars().first()

    if not existing_user or not verify_password(form_data.password, existing_user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expiry = timedelta(minutes=settings.jwt_token_expiry_mins)
    access_token = create_access_token({"sub": str(existing_user.id)}, access_token_expiry)

    set_access_token_cookie(response, access_token)
    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response) -> dict[str, str]:
    """Invalidate the auth cookie on the client (idempotent; token remains valid
    until it expires, but nothing else can read or use the cookie)."""
    clear_access_token_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponsePrivate)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[None, Depends(password_reset_rate_limit)],
):
    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == request_data.email.lower()),
    )
    user = result.scalars().first()

    if user:
        await db.execute(
            sql_delete(models.PasswordResetToken).where(
                models.PasswordResetToken.user_id == user.id,
            ),
        )

        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.reset_expire_token_mins)

        reset_token = models.PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.commit()

        background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,
            username=user.username,
            token=token,
        )

    # Same response whether or not the email exists, to prevent email enumeration
    return {
        "message": (
            "If an account exists with this email, you will receive password reset"
            " instructions."
        )
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    token_hash = hash_reset_token(request_data.token)

    result = await db.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == token_hash,
        ),
    )
    reset_token = result.scalars().first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if reset_token.expires_at < datetime.now(UTC):
        await db.delete(reset_token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(
        select(models.User).where(models.User.id == reset_token.user_id),
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(request_data.new_password)

    # Consume every token so a replayed reset link cannot be used again
    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == user.id,
        ),
    )

    await db.commit()
    return {"message": "Password reset successfully. You can now log in with your new password."}


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(password_data.new_password)

    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == current_user.id,
        ),
    )

    await db.commit()
    return {"message": "Password changed successfully"}


@router.get("/{user_id}", response_model=UserResponsePublic)
async def user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return existing_user


@router.get("/{user_id}/posts", response_model=PaginatedPostResponse)
async def user_post_page(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    count_result = await db.execute(
        select(func.count())
        .select_from(models.Post)
        .where(models.Post.user_id == user_id),
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

    has_more = skip + len(posts) < total

    return PaginatedPostResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.patch("/{user_id}", response_model=UserResponsePrivate, name="update_user_partial")
async def update_user_partial(
    user_id: int,
    updated_user: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to update user")

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if updated_user.username is not None and updated_user.username.lower() != func.lower(
        existing_user.username
    ):
        result = await db.execute(
            select(models.User).where(
                func.lower(models.User.username) == updated_user.username.lower()
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    if updated_user.email is not None and updated_user.email.lower() != func.lower(
        existing_user.email
    ):
        result = await db.execute(
            select(models.User).where(func.lower(models.User.email) == updated_user.email.lower())
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    updated_user_dict = updated_user.model_dump(exclude_unset=True)

    if "email" in updated_user_dict and updated_user_dict["email"]:
        updated_user_dict["email"] = updated_user_dict["email"].lower()

    for field, value in updated_user_dict.items():
        setattr(existing_user, field, value)

    await db.commit()
    await db.refresh(existing_user)
    return existing_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, name="delete_user")
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to delete user")

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    existing_user = result.scalars().first()

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_filename = existing_user.image_file

    await db.delete(existing_user)
    await db.commit()

    if old_filename:
        await delete_profile_image(old_filename)


@router.patch("/{user_id}/picture", response_model=UserResponsePrivate)
async def upload_profile_picture(
    file: UploadFile,
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's profile picture",
        )

    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File size too large. Maximum size is"
                f" {settings.max_upload_size_bytes // (1024 * 1024)} MB"
            ),
        )

    try:
        processed_bytes, new_filename = await run_in_threadpool(process_profile_image, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err

    try:
        await upload_profile_image(processed_bytes, new_filename)
    except ClientError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image. Please try again.",
        ) from err

    old_filename = current_user.image_file

    current_user.image_file = new_filename

    await db.commit()
    await db.refresh(current_user)

    if old_filename:
        await delete_profile_image(old_filename)

    return current_user


@router.delete("/{user_id}/picture", response_model=UserResponsePrivate)
async def delete_user_picture(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user's profile picture",
        )

    old_file_name = current_user.image_file

    if old_file_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete",
        )

    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    await delete_profile_image(old_file_name)

    return current_user