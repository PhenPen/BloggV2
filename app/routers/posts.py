"""Post CRUD API routes mounted at ``/api/posts``."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import models
from app.auth import CurrentUser
from app.database import get_db_session
from app.schemas import PaginatedPostResponse, PostCreate, PostResponse, PostUpdate

router = APIRouter()


async def _get_post_or_404(
    db: AsyncSession, post_id: int
) -> models.Post:
    """Return a post with its author eager-loaded, or raise 404."""
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    existing_post = result.scalars().first()
    if not existing_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return existing_post


def _ensure_ownership(post: models.Post, current_user: models.User) -> None:
    """Raise 403 unless the current user owns the post."""
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this post",
        )


@router.get("", response_model=PaginatedPostResponse, name="posts")
async def list_posts(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    total_post_count_query = await db.execute(
        select(func.count()).select_from(models.Post)
    )
    total_post_count = total_post_count_query.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit)
    )
    posts = result.scalars().all()

    has_more = (skip + len(posts)) < total_post_count

    return PaginatedPostResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        total=total_post_count,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.get("/{post_id}", response_model=PostResponse, name="post")
async def get_post(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await _get_post_or_404(db, post_id)


@router.put("/{post_id}", response_model=PostResponse, name="update_post_full")
async def update_post_full(
    post_id: int,
    updated_post: PostCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    existing_post = await _get_post_or_404(db, post_id)
    _ensure_ownership(existing_post, current_user)

    existing_post.title = updated_post.title
    existing_post.content = updated_post.content

    await db.commit()
    await db.refresh(existing_post, attribute_names=["author"])
    return existing_post


@router.patch("/{post_id}", response_model=PostResponse, name="update_post_partial")
async def update_post_partial(
    post_id: int,
    updated_post: PostUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    existing_post = await _get_post_or_404(db, post_id)
    _ensure_ownership(existing_post, current_user)

    # exclude_unset=True keeps fields the client did not send untouched
    updated_post_dict = updated_post.model_dump(exclude_unset=True)
    for field, value in updated_post_dict.items():
        setattr(existing_post, field, value)

    await db.commit()
    await db.refresh(existing_post, attribute_names=["author"])
    return existing_post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, name="delete_post")
async def delete_post(
    post_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    existing_post = await _get_post_or_404(db, post_id)
    _ensure_ownership(existing_post, current_user)

    await db.delete(existing_post)
    await db.commit()


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post: PostCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    # Ownership comes from the authenticated user, never from the request body
    new_post = models.Post(
        title=post.title, content=post.content, user_id=current_user.id
    )

    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])

    return new_post