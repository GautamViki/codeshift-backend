from fastapi import Request
from fastapi.responses import JSONResponse

from app.helpers.logger import logger
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI


class TranspilerError(Exception):
    status_code: int = 400
    app_code: int = 1000
    default_message: str = "An error occurred during transpilation."
    error_type: str = "TRANSPILER_ERROR"

    def __init__(self, message: str = None, **extra):
        self.message = message or self.default_message
        self.extra = extra
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "success": False,
            "code": self.app_code,
            "error_type": self.error_type,
            "message": self.message,
            **self.extra,
        }


# ---- Input errors ----

class InvalidPythonSyntaxError(TranspilerError):
    status_code = 400
    app_code = 1001
    default_message = "The provided Python source code is not valid."
    error_type = "INVALID_INPUT"


class UnsupportedLanguageError(TranspilerError):
    status_code = 400
    app_code = 1002
    default_message = "This source/target language combination is not supported."
    error_type = "UNSUPPORTED_LANGUAGE"


class InvalidFileEncodingError(TranspilerError):
    status_code = 400
    app_code = 1003
    default_message = "Uploaded content is not valid UTF-8 text."
    error_type = "INVALID_FILE_ENCODING"


# ---- LLM / provider errors ----

class LLMProviderError(TranspilerError):
    status_code = 502
    app_code = 2000
    default_message = "The AI provider returned an unexpected error."
    error_type = "PROVIDER_ERROR"


class RateLimitExceededError(LLMProviderError):
    status_code = 429
    app_code = 2001
    default_message = "API quota exceeded. Please retry later or check your plan."
    error_type = "RATE_LIMIT_EXCEEDED"


class InvalidApiKeyError(LLMProviderError):
    status_code = 401
    app_code = 2002
    default_message = "The configured API key is invalid or missing."
    error_type = "INVALID_API_KEY"


class PermissionDeniedError(LLMProviderError):
    status_code = 403
    app_code = 2003
    default_message = "Access to this model or resource was denied."
    error_type = "PERMISSION_DENIED"


class ProviderUnavailableError(LLMProviderError):
    status_code = 503
    app_code = 2004
    default_message = "The AI provider is temporarily unavailable. Please retry."
    error_type = "PROVIDER_UNAVAILABLE"


class EmptyLLMResponseError(TranspilerError):
    status_code = 502
    app_code = 2005
    default_message = "The AI provider returned an empty or unusable response."
    error_type = "EMPTY_LLM_RESPONSE"


# ---- Output validation errors ----

class GoValidationError(TranspilerError):
    status_code = 422
    app_code = 3001
    default_message = "The generated Go code failed compilation/validation."
    error_type = "GO_VALIDATION_FAILED"


class GoToolingUnavailableError(TranspilerError):
    status_code = 500
    app_code = 3002
    default_message = "Go tooling (go vet/gofmt) is not available on this server."
    error_type = "GO_TOOLING_UNAVAILABLE"


# ---- File system errors ----

class FileWriteError(TranspilerError):
    status_code = 500
    app_code = 4001
    default_message = "Failed to save the generated code to disk."
    error_type = "FILE_WRITE_ERROR"


class CodeValidationError(TranspilerError):
    status_code = 422
    app_code = 3001
    default_message = "The generated code failed validation."
    error_type = "CODE_VALIDATION_FAILED"


class ValidationToolUnavailableError(TranspilerError):
    status_code = 500
    app_code = 3002
    default_message = "Validation tooling is not available on this server."
    error_type = "VALIDATION_TOOL_UNAVAILABLE"


# ---- Auth, Database & Resource errors ----

class AuthenticationError(TranspilerError):
    status_code = 401
    app_code = 4001
    default_message = "Authentication failed."
    error_type = "AUTHENTICATION_FAILED"


class ConflictError(TranspilerError):
    status_code = 409
    app_code = 4009
    default_message = "Resource already exists."
    error_type = "CONFLICT_ERROR"


class ValidationError(TranspilerError):
    status_code = 422
    app_code = 4022
    default_message = "Validation error."
    error_type = "VALIDATION_ERROR"


class DatabaseError(TranspilerError):
    status_code = 503
    app_code = 5001
    default_message = "Database service is temporarily unavailable. Please retry later."
    error_type = "DATABASE_ERROR"


class ExceptionHandler:
    FIELD_MESSAGES = {
        "file": "Source file is required. Upload it as form-data field 'file'.",
        "target_language": "Target language is required, e.g. 'go' or 'python'.",
        "email": "A valid email address is required.",
        "password": "Password is required.",
    }

    def __init__(self, app: FastAPI):
        self.app = app

    async def transpiler_exception(self, request: Request, exc: TranspilerError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    async def sqlalchemy_exception(self, request: Request, exc: Exception):
        logger.error(
            f"Database error on {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "code": 5001,
                "error_type": "DATABASE_ERROR",
                "message": "Database is temporarily unavailable. Please try again later.",
            },
        )

    async def unhandled_exception(self, request: Request, exc: Exception):
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

    async def validation_exception(self, request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            field = str(err["loc"][-1]) if err["loc"] else "unknown"
            message = (
                self.FIELD_MESSAGES.get(field, f"'{field}' is required.")
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

    async def http_exception(self, request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": "HTTP_ERROR", "message": exc.detail},
        )

    def register_exception(self) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        self.app.add_exception_handler(TranspilerError, self.transpiler_exception)
        self.app.add_exception_handler(RequestValidationError, self.validation_exception)
        self.app.add_exception_handler(StarletteHTTPException, self.http_exception)
        self.app.add_exception_handler(SQLAlchemyError, self.sqlalchemy_exception)
        self.app.add_exception_handler(Exception, self.unhandled_exception)