# app/handlers/auth_handlers.py
from fastapi import Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth import AuthService

auth_service = AuthService()


async def register(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register(db, email, password)
    return {"id": user.id, "email": user.email}


async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    token = await auth_service.login(db, email, password)
    return {"access_token": token, "token_type": "bearer"}