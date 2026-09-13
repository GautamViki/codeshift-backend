from fastapi import Request
from fastapi.responses import JSONResponse

from app.helpers.exceptions import TranspilerError
from app.helpers.logger import logger


async def transpiler_exception_handler(request: Request, exc: TranspilerError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 9999,
            "error_type": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "path": request.url.path,
        },
    )