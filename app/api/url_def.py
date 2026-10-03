from fastapi import APIRouter
from app.handlers import auth_handler, history_handlers
from app.handlers import transpile_handlers as h

router = APIRouter(prefix="/api/v1")

# Transpilation routes
router.add_api_route(
    "/transpile-file",
    h.transpile_file,
    methods=["POST"],
    tags=["transpile"],
    summary="Transpile an uploaded source file",
    responses={
        400: {"description": "Unsupported language or invalid file"},
        401: {"description": "Invalid or missing bearer token"},
        422: {"description": "Validation error"},
    },
)

router.add_api_route(
    "/transpile-raw",
    h.transpile_raw,
    methods=["POST"],
    tags=["transpile"],
    summary="Transpile code sent as a plain text body",
    responses={
        401: {"description": "Invalid or missing bearer token"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/plain": {"schema": {"type": "string"}}},
        }
    },
)

# Authentication routes
router.add_api_route(
    "/auth/register",
    auth_handler.register,
    methods=["POST"],
    tags=["auth"],
    summary="Register a new user",
    responses={
        409: {"description": "An account with this email already exists"},
        422: {"description": "Validation error"},
    },
)

router.add_api_route(
    "/auth/login",
    auth_handler.login,
    methods=["POST"],
    tags=["auth"],
    summary="Log in user to obtain access token",
    responses={
        401: {"description": "Incorrect email or password"},
        422: {"description": "Validation error"},
    },
)

# History routes
router.add_api_route(
    "/history",
    history_handlers.get_history,
    methods=["GET"],
    tags=["history"],
    summary="Get user transpilation history",
    responses={
        401: {"description": "Invalid or missing bearer token"},
        422: {"description": "Validation error"},
    },
)