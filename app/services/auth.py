# app/services/auth.py
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.helpers import logger, exceptions as err


class AuthService:
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "codeshift-dev-secret-key-change-in-production-long-random-string")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    @staticmethod
    def _hash_password(password: str) -> str:
        pwd_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    @staticmethod
    def _verify_password(plain_password: str, hashed_password: str) -> bool:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)

    async def register(self, db: AsyncSession, email: str, password: str) -> User:
        email = email.strip().lower()
        try:
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                raise err.ConflictError("An account with this email already exists.")

            user = User(
                email=email,
                hashed_password=self._hash_password(password),
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user
        except err.TranspilerError:
            raise
        except Exception as exc:
            await db.rollback()
            from sqlalchemy.exc import IntegrityError, SQLAlchemyError
            if isinstance(exc, IntegrityError):
                raise err.ConflictError("An account with this email already exists.")
            if isinstance(exc, SQLAlchemyError):
                logger.error(f"Database error during registration: {exc}", exc_info=True)
                raise err.DatabaseError()
            raise


    async def login(self, db: AsyncSession, email: str, password: str) -> str:
        email = email.strip().lower()
        try:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user or not self._verify_password(password, user.hashed_password):
                raise err.AuthenticationError("Incorrect email or password.")

            return self._create_token(user.id)
        except err.TranspilerError:
            raise
        except Exception as exc:
            from sqlalchemy.exc import SQLAlchemyError
            if isinstance(exc, SQLAlchemyError):
                logger.error(f"Database error during login: {exc}", exc_info=True)
                raise err.DatabaseError()
            raise


    async def get_current_user(self, db: AsyncSession, token: str) -> User:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError):
            raise err.AuthenticationError("Invalid or expired token.")

        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                raise err.AuthenticationError("User no longer exists.")
            return user
        except err.TranspilerError:
            raise
        except Exception as exc:
            from sqlalchemy.exc import SQLAlchemyError
            if isinstance(exc, SQLAlchemyError):
                logger.error(f"Database error during get_current_user: {exc}", exc_info=True)
                raise err.DatabaseError()
            raise


    def _create_token(self, user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        return jwt.encode({"sub": str(user_id), "exp": expire}, self.SECRET_KEY, algorithm=self.ALGORITHM)