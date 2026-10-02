from datetime import datetime
from typing import TYPE_CHECKING

from chromadb import db
from sqlalchemy import ForeignKey, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

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
        UniqueConstraint("source_hash", "target_language", name="uq_source_target"),
    )

    async def find_cached_transpilation(
            self, source_code: str, source_language: str, target_language: str
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

    async def save_transpilation(
            self,
            user_id: int,
            source_code: str,
            source_language: str,
            target_language: str,
            transpiled_code: str,
            validated: bool,
    ) -> Transpilation:
        """Write-only. Inserts a new row, owned by user_id from the start."""
        source_hash = generate_hash(source_code, source_language, target_language)
        new_row = Transpilation(
            user_id=user_id,
            source_hash=source_hash,
            source_language=source_language,
            target_language=target_language,
            source_code=source_code,
            transpiled_code=transpiled_code,
            validated=validated,
        )
        db.add(new_row)
        await db.commit()
        await db.refresh(new_row)
        return new_row