from fastapi import APIRouter

from app.handlers import transpile_handlers as h

router = APIRouter(prefix="/api/v1", tags=["transpile"])

router.add_api_route(
    "/transpile-file",
    h.transpile_file,
    methods=["POST"],
    summary="Transpile an uploaded source file",
    responses={
        400: {"description": "Unsupported language or invalid file"},
        422: {"description": "Validation error"},
    },
)

router.add_api_route(
    "/transpile-raw",
    h.transpile_raw,
    methods=["POST"],
    summary="Transpile code sent as a plain text body",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/plain": {"schema": {"type": "string"}}},
        }
    },
)