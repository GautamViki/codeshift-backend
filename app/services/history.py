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
        logger.info("Checking user transpilation history for existing record")
        result = await session.execute(
            select(Transpilation).where(
                Transpilation.user_id == user_id,
                Transpilation.source_hash == source_hash,
                Transpilation.target_language == target_language,
            )
        )
        existing = result.scalar_one_or_none()
        logger.info(
            "Existing transpilation record lookup completed | found=%s", existing is not None
        )
        return existing

    async def find_cached(
        self, db: AsyncSession, source_code: str, source_language: str, target_language: str
    ) -> Transpilation | None:
        """Read-only lookup by content hash, across all users."""
        logger.info("Cached transpilation history lookup started")
        source_hash = generate_hash(source_code, source_language, target_language)
        try:
            result = await db.execute(
                select(Transpilation).where(
                    Transpilation.source_hash == source_hash,
                    Transpilation.target_language == target_language,
                )
            )
            existing = result.scalar_one_or_none()
            logger.info(
                "Cached transpilation history lookup completed | found=%s", existing is not None
            )
            return existing
        except (SQLAlchemyError, ConnectionError) as exc:
            logger.error(
                "Database exception during cached transpilation lookup | type=%s | message=%s",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise err.DatabaseError() from exc

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
        logger.info(
            "Transpilation history save started | user_id=%s | source=%s | target=%s",
            user_id,
            source_language,
            target_language,
        )
        source_hash = generate_hash(source_code, source_language, target_language)
        async with SessionLocal() as session:
            try:
                existing = await self._find_existing(session, user_id, source_hash, target_language)
                if existing is not None:
                    logger.info("Reusing existing transpilation history record")
                    return existing

                logger.info("Creating transpilation history record")
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
                logger.info("Transpilation history save completed")
                return row
            except IntegrityError as exc:
                await session.rollback()
                existing = await self._find_existing(session, user_id, source_hash, target_language)
                if existing is not None:
                    logger.info("Reusing concurrently created transpilation history record")
                    return existing
                logger.error(
                    "Database exception while saving transpilation history | type=%s | message=%s",
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                raise err.DatabaseError() from exc
            except (SQLAlchemyError, ConnectionError) as exc:
                await session.rollback()
                logger.error(
                    "Database exception while saving transpilation history | type=%s | message=%s",
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                raise err.DatabaseError() from exc

    async def list_for_user(
        self, db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[Transpilation]:
        """Read-only. A user's own history, most recent first."""
        logger.info(
            "User transpilation history query started | user_id=%s | limit=%s | offset=%s",
            user_id,
            limit,
            offset,
        )
        try:
            result = await db.execute(
                select(Transpilation)
                .where(Transpilation.user_id == user_id)
                .order_by(Transpilation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = list(result.scalars())
            logger.info("User transpilation history query completed | records=%s", len(rows))
            return rows
        except (SQLAlchemyError, ConnectionError) as exc:
            logger.error(
                "Database exception while listing history for user %s | type=%s | message=%s",
                user_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise err.DatabaseError() from exc
