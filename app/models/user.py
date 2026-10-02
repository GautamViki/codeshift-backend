from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.transpilation import Transpilation


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phone_number = Column(String, nullable=True)

    transpilations: Mapped[list["Transpilation"]] = relationship(back_populates="user")



    async def record_history(self, user_id: int, transpilation_id: int) -> None:
        """
        Write-only. Links an existing transpilation to a user's history
        (used on a cache hit, so the user sees it in their own history
        without duplicating the stored code).
        """
        entry = UserHistory(user_id=user_id, transpilation_id=transpilation_id)
        db.add(entry)
        await db.commit()