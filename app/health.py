"""Health-check endpoints for load balancers and container healthchecks."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Process accepts requests (no external dependency)."""
    return {"status": "ok"}


@router.get("/health")
async def readiness(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Process is live AND can reach PostgreSQL."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return {"status": "ok"}