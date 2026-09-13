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