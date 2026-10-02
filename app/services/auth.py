# app/services/auth.py
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.helpers import exceptions as err


class AuthService:
    SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    def __init__(self):
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def register(self, db: AsyncSession, email: str, password: str) -> User:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise err.TranspilerError("An account with this email already exists.", status_code=409)

        user = User(
            email=email,
            hashed_password=self._pwd_context.hash(password),
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def login(self, db: AsyncSession, email: str, password: str) -> str:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not self._pwd_context.verify(password, user.hashed_password):
            raise err.TranspilerError("Incorrect email or password.", status_code=401)

        return self._create_token(user.id)

    async def get_current_user(self, db: AsyncSession, token: str) -> User:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError):
            raise err.TranspilerError("Invalid or expired token.", status_code=401)

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise err.TranspilerError("User no longer exists.", status_code=401)
        return user

    def _create_token(self, user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        return jwt.encode({"sub": str(user_id), "exp": expire}, self.SECRET_KEY, algorithm=self.ALGORITHM)