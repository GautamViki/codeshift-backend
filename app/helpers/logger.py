import logging
import warnings
import os
from pathlib import Path
from logging.handlers import WatchedFileHandler
from starlette.responses import Response
from fastapi import Request
from http import HTTPStatus

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"


class AppLogger:
    LOG_DIR = Path("logs")
    LOG_FILE = LOG_DIR / "app.log"

    def __init__(self, name: str = "transpiler"):
        self.name = name
        self.logger = self.setup_logger()

    def setup_logger(self, name: str = "transpiler") -> logging.Logger:
        logger = logging.getLogger(name)

        if logger.handlers:  # avoid duplicate helpers on reload
            return logger

        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Only write to file (and echo to console) in local/dev
        if os.getenv("ENVIRONMENT", "development") == "development":
            file_handler = WatchedFileHandler(LOG_FILE, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

        return logger


    async def log_requests(self, request: Request, call_next):
        self.logger.info(f"Incoming request: {request.method} {request.url.path}")
        response = await call_next(request)

        if response.status_code >= HTTPStatus.BAD_REQUEST:
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk

            try:
                body_text = body_bytes.decode("utf-8")
            except Exception:
                body_text = "<non-utf8 body>"

            self.logger.info(f"Response status: {response.status_code} for {request.url.path} | detail: {body_text}")

            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        self.logger.info(f"Response status: {response.status_code} for {request.url.path}")
        return response

    def configure_warnings(self):
        warnings.filterwarnings(
            "ignore",
            message="Model 'gemini-3.6-flash' uses fixed sampling defaults.*",
            category=UserWarning,
            module="langchain_google_genai.chat_models",
        )
        logging.getLogger("google_genai.models").setLevel(logging.ERROR)
        logging.getLogger("google_genai").setLevel(logging.ERROR)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

logger = AppLogger()