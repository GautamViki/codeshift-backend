from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.helpers import exceptions as err
from app.helpers import logger
from app.helpers.utils import generate_hash
from app.models.transpilation import Transpilation


class TranspilationHistoryService:
    async def _find_existing(
        self,
        session: AsyncSession,
        user_id: int,
        source_hash: str,
        target_language: str,
    ) -> Transpilation | None:
        result = await session.execute(
            select(Transpilation).where(
                Transpilation.user_id == user_id,
                Transpilation.source_hash == source_hash,
                Transpilation.target_language == target_language,
            )
        )
        return result.scalar_one_or_none()

    async def find_cached(
        self, db: AsyncSession, source_code: str, source_language: str, target_language: str
    ) -> Transpilation | None:
        """Read-only lookup by content hash, across all users."""
        source_hash = generate_hash(source_code, source_language, target_language)
        try:
            result = await db.execute(
                select(Transpilation).where(
                    Transpilation.source_hash == source_hash,
                    Transpilation.target_language == target_language,
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.error(f"Database error looking up cached transpilation: {exc}", exc_info=True)
            raise err.DatabaseError()

    async def save(
        self,
        user_id: int,
        source_code: str,
        source_language: str,
        target_language: str,
        transpiled_code: str,
        validated: bool,
        validation_message: str | None = None,
    ) -> Transpilation:
        """Save a transpilation using a session owned by this operation."""
        source_hash = generate_hash(source_code, source_language, target_language)
        async with SessionLocal() as session:
            try:
                existing = await self._find_existing(session, user_id, source_hash, target_language)
                if existing is not None:
                    return existing

                row = Transpilation(
                    user_id=user_id,
                    source_hash=source_hash,
                    source_language=source_language,
                    target_language=target_language,
                    source_code=source_code,
                    transpiled_code=transpiled_code,
                    validated=validated,
                    validation_message=validation_message,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
                return row
            except IntegrityError as exc:
                await session.rollback()
                existing = await self._find_existing(session, user_id, source_hash, target_language)
                if existing is not None:
                    return existing
                logger.error(
                    "Database integrity error saving transpilation history.", exc_info=True
                )
                raise err.DatabaseError() from exc
            except SQLAlchemyError as exc:
                await session.rollback()
                logger.error(f"Database error saving transpilation history: {exc}", exc_info=True)
                raise err.DatabaseError() from exc

    async def list_for_user(
        self, db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[Transpilation]:
        """Read-only. A user's own history, most recent first."""
        try:
            result = await db.execute(
                select(Transpilation)
                .where(Transpilation.user_id == user_id)
                .order_by(Transpilation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars())
        except SQLAlchemyError as exc:
            logger.error(
                f"Database error listing transpilation history for user {user_id}: {exc}",
                exc_info=True,
            )
            raise err.DatabaseError()
