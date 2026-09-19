from app.helpers.logger import logger
from contextlib import asynccontextmanager
from fastapi import FastAPI

async def on_startup():
    logger.info("=" * 50)
    logger.info("Polyglot Refactor Engine started successfully")
    logger.info("=" * 50)


async def on_shutdown():
    logger.info("Polyglot Refactor Engine shutting down")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()