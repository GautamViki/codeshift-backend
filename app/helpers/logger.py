import logging
import time
import warnings
from contextvars import ContextVar
from http import HTTPStatus
from logging.handlers import WatchedFileHandler
from pathlib import Path
from secrets import token_hex

from fastapi import Request
from starlette.responses import Response

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class AppLogger:
    LOG_DIR = Path("logs")
    LOG_FILE = LOG_DIR / "app.log"

    def __init__(self, name: str = "transpiler"):
        self.name = name
        self.logger = self.setup_logger()

    def setup_logger(self, name: str = "transpiler") -> logging.Logger:
        logger = logging.getLogger(name)
        if not any(isinstance(log_filter, RequestIdFilter) for log_filter in logger.filters):
            logger.addFilter(RequestIdFilter())

        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                logger.removeHandler(handler)
                handler.close()

        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(request_id)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if not any(isinstance(handler, WatchedFileHandler) for handler in logger.handlers):
            file_handler = WatchedFileHandler(LOG_FILE, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    async def log_requests(self, request: Request, call_next):
        request_id = token_hex(6)
        request.state.request_id = request_id
        context_token = request_id_context.set(request_id)
        request_details = f"{request.method} {request.url.path}"
        started_at = time.perf_counter()
        try:
            self.logger.info("Incoming request: %s", request_details)

            try:
                response = await call_next(request)
            except Exception as exc:
                duration_ms = (time.perf_counter() - started_at) * 1000
                self.logger.error(
                    "Request exception | request=%s | type=%s | message=%s | duration_ms=%.2f",
                    request_details,
                    type(exc).__name__,
                    exc,
                    duration_ms,
                )
                raise

            response.headers["X-Request-ID"] = request_id
            if response.status_code >= HTTPStatus.BAD_REQUEST:
                body_bytes = b""
                async for chunk in response.body_iterator:
                    body_bytes += chunk

                try:
                    body_text = body_bytes.decode("utf-8")
                except Exception as exc:
                    self.logger.error(
                        "Response body decode exception | type=%s | message=%s",
                        type(exc).__name__,
                        exc,
                    )
                    body_text = "<non-utf8 body>"

                self.logger.info(
                    "Response status: %s for %s | duration_ms=%.2f | detail: %s",
                    response.status_code,
                    request_details,
                    (time.perf_counter() - started_at) * 1000,
                    body_text,
                )

                return Response(
                    content=body_bytes,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

            self.logger.info(
                "Response status: %s for %s | duration_ms=%.2f",
                response.status_code,
                request_details,
                (time.perf_counter() - started_at) * 1000,
            )
            return response
        finally:
            request_id_context.reset(context_token)

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
