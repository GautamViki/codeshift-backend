from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Transpilation(Base):
    __tablename__ = "transpilations"

    def __init__(
        self,
        *,
        user_id: int,
        source_language: str,
        target_language: str,
        source_code: str,
        transpiled_code: str,
        source_hash: str,
        validated: bool,
        validation_message: str | None,
        created_at: datetime,
    ) -> None:
        self.user_id = user_id
        self.source_language = source_language
        self.target_language = target_language
        self.source_code = source_code
        self.transpiled_code = transpiled_code
        self.source_hash = source_hash
        self.validated = validated
        self.validation_message = validation_message
        self.created_at = created_at

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    source_language: Mapped[str]
    target_language: Mapped[str]
    source_code: Mapped[str] = mapped_column(Text)
    transpiled_code: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(index=True)

    validated: Mapped[bool] = mapped_column(default=False)
    validation_message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="transpilations")

    __table_args__ = (
        UniqueConstraint("user_id", "source_hash", "target_language", name="uq_user_source_target"),
    )
