from app.helpers.exceptions import LLMProviderError
from app.helpers.constants import LANGUAGE_EXTENSIONS, LANGUAGE_START_MARKERS, GOOGLE_ERROR_MAP
from app.validators.go_validator import validate_go_code

def handle_llm_error(self, exc: Exception, source_language: str, target_language: str):
    """Maps a Google/LangChain exception to the matching TranspilerError subclass,
    logging at the appropriate severity before raising."""
    for exc_type, (mapped_exc, log_fn, log_prefix) in GOOGLE_ERROR_MAP.items():
        if isinstance(exc, exc_type):
            log_fn(f"{log_prefix} ({source_language}->{target_language}): {exc}")
            raise mapped_exc(self._extract_clean_message(exc, str(exc))) from exc
    raise LLMProviderError(str(exc)) from exc

# Optional post-generation validators — only languages with real tooling
# available get one; others simply skip validation.
OUTPUT_VALIDATORS = {
    "go": validate_go_code,
}

def get_extension(language: str) -> str:
    return LANGUAGE_EXTENSIONS.get(language.lower(), "txt")


def get_start_marker(language: str) -> str | None:
    return LANGUAGE_START_MARKERS.get(language.lower())


def get_validator(language: str):
    return OUTPUT_VALIDATORS.get(language.lower())