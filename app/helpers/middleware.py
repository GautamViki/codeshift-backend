from starlette.responses import Response
from fastapi import Request

from app.helpers.logger import logger


async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)

    if response.status_code >= 400:
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        try:
            body_text = body_bytes.decode("utf-8")
        except Exception:
            body_text = "<non-utf8 body>"

        logger.info(f"Response status: {response.status_code} for {request.url.path} | detail: {body_text}")

        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    logger.info(f"Response status: {response.status_code} for {request.url.path}")
    return response