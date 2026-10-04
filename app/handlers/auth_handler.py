import re

from fastapi import Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.helpers import exceptions, logger
from app.services.auth import AuthService

auth_service = AuthService()

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def register(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    logger.info("Registration request started")
    email = email.strip()
    if not email or not EMAIL_REGEX.match(email):
        raise exceptions.ValidationError("Please provide a valid email address.")
    if len(password) < 6:
        raise exceptions.ValidationError("Password must be at least 6 characters long.")
    if len(password.encode("utf-8")) > 72:
        raise exceptions.ValidationError("Password cannot exceed 72 bytes.")

    logger.info("Registration input validated; creating account")
    user = await auth_service.register(db, email, password)
    logger.info("Registration completed")
    return {"id": user.id, "email": user.email}


async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    logger.info("Login request started")
    email = email.strip()
    if not email:
        raise exceptions.ValidationError("Email is required.")
    if not password:
        raise exceptions.ValidationError("Password is required.")

    token = await auth_service.login(db, email, password)
    logger.info("Login completed")
    return {
        "success": True,
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
    }
