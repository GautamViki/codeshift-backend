# app/services/history.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transpilation import Transpilation
from app.helpers.hashing import generate_hash


class TranspilationHistoryService:
    async def find_cached(
        self, db: AsyncSession, source_code: str, source_language: str, target_language: str
    ) -> Transpilation | None:
        """Read-only lookup by content hash, across all users."""
        source_hash = generate_hash(source_code, source_language, target_language)
        result = await db.execute(
            select(Transpilation).where(
                Transpilation.source_hash == source_hash,
                Transpilation.target_language == target_language,
            )
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        db: AsyncSession,
        user_id: int,
        source_code: str,
        source_language: str,
        target_language: str,
        transpiled_code: str,
        validated: bool,
    ) -> Transpilation:
        """Write-only. Inserts a new row, owned by user_id."""
        source_hash = generate_hash(source_code, source_language, target_language)
        row = Transpilation(
            user_id=user_id,
            source_hash=source_hash,
            source_language=source_language,
            target_language=target_language,
            source_code=source_code,
            transpiled_code=transpiled_code,
            validated=validated,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def list_for_user(
        self, db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[Transpilation]:
        """Read-only. A user's own history, most recent first."""
        result = await db.execute(
            select(Transpilation)
            .where(Transpilation.user_id == user_id)
            .order_by(Transpilation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars())