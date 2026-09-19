from fastapi import Request
from fastapi.responses import JSONResponse

from app.helpers.exceptions import TranspilerError
from app.helpers.logger import logger
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI


FIELD_MESSAGES = {
    "file": "Source file is required. Upload it as form-data field 'file'.",
    "target_language": "Target language is required, e.g. 'go' or 'python'.",
}

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

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        field = str(err["loc"][-1]) if err["loc"] else "unknown"
        message = (
            FIELD_MESSAGES.get(field, f"'{field}' is required.")
            if err["type"] == "missing"
            else err["msg"]
        )
        details.append({"field": field, "message": message})

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Invalid request.",
            "details": details,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": "HTTP_ERROR", "message": exc.detail},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TranspilerError, transpiler_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)