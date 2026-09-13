from app.helpers.logger import logger


async def on_startup():
    logger.info("=" * 50)
    logger.info("Polyglot Refactor Engine started successfully")
    logger.info("=" * 50)


async def on_shutdown():
    logger.info("Polyglot Refactor Engine shutting down")