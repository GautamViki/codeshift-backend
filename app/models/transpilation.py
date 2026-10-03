from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, SessionLocal
from app.helpers.utils import generate_hash

if TYPE_CHECKING:
    from app.models.user import User


class Transpilation(Base):
    __tablename__ = "transpilations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    source_language: Mapped[str]
    target_language: Mapped[str]
    source_code: Mapped[str] = mapped_column(Text)
    transpiled_code: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(index=True)

    validated: Mapped[bool] = mapped_column(default=False)
    validation_message: Mapped[str | None]
    created_at: Mapped[datetime]

    user: Mapped["User"] = relationship(back_populates="transpilations")

    __table_args__ = (
        UniqueConstraint("user_id", "source_hash", "target_language", name="uq_user_source_target"),
    )

    @staticmethod
    async def find_cached_transpilation(
            db: AsyncSession, source_code: str, source_language: str, target_language: str
    ) -> "Transpilation | None":
        """Read-only lookup by content hash, across all users."""
        source_hash = generate_hash(source_code, source_language, target_language)
        result = await db.execute(
            select(Transpilation).where(
                Transpilation.source_hash == source_hash,
                Transpilation.target_language == target_language,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_transpilation(
            user_id: int,
            source_code: str,
            source_language: str,
            target_language: str,
            transpiled_code: str,
            validated: bool,
            validation_message: str | None = None,
    ) -> "Transpilation":
        """
        Opens its own database session. Checks if this exact combo was
        already transpiled for this user; if so, returns the existing row.
        Otherwise inserts and returns the new row.
        """
        source_hash = generate_hash(source_code, source_language, target_language)

        async with SessionLocal() as db:
            existing = await db.execute(
                select(Transpilation).where(
                    Transpilation.user_id == user_id,
                    Transpilation.source_hash == source_hash,
                    Transpilation.target_language == target_language,
                )
            )
            existing_row = existing.scalar_one_or_none()
            if existing_row:
                return existing_row

            new_row = Transpilation(
                user_id=user_id,
                source_hash=source_hash,
                source_language=source_language,
                target_language=target_language,
                source_code=source_code,
                transpiled_code=transpiled_code,
                validated=validated,
                validation_message=validation_message,
                created_at=datetime.utcnow(),
            )
            db.add(new_row)
            await db.commit()
            await db.refresh(new_row)
            return new_row