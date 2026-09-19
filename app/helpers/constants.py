from langchain_google_genai.chat_models import (
    GoogleRateLimitError, GoogleAuthenticationError,
    GooglePermissionDeniedError, ChatGoogleGenerativeAIError,
)

from app.helpers.exceptions import RateLimitExceededError, PermissionDeniedError, InvalidApiKeyError, LLMProviderError
from app.helpers.logger import logger

# Gemini model configuration
GEMINI_MODEL_NAME = "gemini-3.6-flash"
GEMINI_TEMPERATURE = 0.1
THINKING_BUDGET = 0

# Maps a Google/LangChain exception type to: (our exception class, log function, log prefix).
# Order matters — more specific exception types must come before their parent classes,
# since GoogleRateLimitError/GoogleAuthenticationError/GooglePermissionDeniedError all
# inherit from ChatGoogleGenerativeAIError.
GOOGLE_ERROR_MAP = {
    GoogleRateLimitError: (RateLimitExceededError, logger.warning, "Gemini rate limit hit"),
    GoogleAuthenticationError: (InvalidApiKeyError, logger.error, "Gemini authentication failed"),
    GooglePermissionDeniedError: (PermissionDeniedError, logger.error, "Gemini permission denied"),
    ChatGoogleGenerativeAIError: (LLMProviderError, logger.error, "Gemini call failed"),
}

LANGUAGE_EXTENSIONS = {
    "python": "py",
    "go": "go",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "rust": "rs",
}

LANGUAGE_START_MARKERS = {
    "go": r'\bpackage\s+\w+',
    "java": r'\b(public\s+)?class\s+\w+',
    "python": r'^(import|from|def|class)\s',
    # languages without a strong marker fall back to no trimming
}

MAX_CODE_BYTES = 1_000_000