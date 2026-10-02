# app/handlers/history_handlers.py
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.history import TranspilationHistoryService
from app.services.auth import AuthService
from app.models.user import User

history_service = TranspilationHistoryService()
auth_service = AuthService()


async def get_history(
    user: User = Depends(auth_service.get_current_user),  # see note below
    limit: int = Query(20),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    rows = await history_service.list_for_user(db, user.id, limit, offset)
    return [{"id": r.id, "source_language": r.source_language, "target_language": r.target_language, "created_at": r.created_at} for r in rows]