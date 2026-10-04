from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.helpers import logger
from app.models.user import User
from app.services.history import TranspilationHistoryService

history_service = TranspilationHistoryService()


async def get_history(
    user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100, description="Number of records to retrieve (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    logger.info("History retrieval started | limit=%s | offset=%s", limit, offset)
    rows = await history_service.list_for_user(db, user.id, limit, offset)
    logger.info("History retrieval completed | records=%s", len(rows))
    return [
        {
            "id": r.id,
            "source_language": r.source_language,
            "target_language": r.target_language,
            "created_at": r.created_at,
        }
        for r in rows
    ]
