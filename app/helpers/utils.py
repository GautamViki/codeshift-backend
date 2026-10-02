import re
from app.helpers.exceptions import LLMProviderError
from app.helpers.constants import LANGUAGE_EXTENSIONS, LANGUAGE_START_MARKERS, GOOGLE_ERROR_MAP
from app.validators.code_validator import ValidationFactory
import hashlib


def extract_clean_message(exc: Exception, fallback: str) -> str:
    text = str(exc)
    original = getattr(exc, "__cause__", None)
    if original is not None:
        text = str(original)
        if hasattr(original, "details"):
            details = original.details
            if isinstance(details, dict):
                msg = details.get("error", {}).get("message")
                if msg:
                    return msg.replace("\\n", "\n").split("\n")[0].strip()

    # Search for nested error message in JSON-like strings
    match = re.search(r'"message":\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
    if match:
        try:
            clean = match.group(1).replace("\\\\n", "\n").replace("\\n", "\n").split("\n")[0].strip()
            if clean:
                return clean
        except Exception:
            pass

    return fallback.replace("\\\\n", "\n").replace("\\n", "\n").split("\n")[0].strip()


def handle_llm_error(exc: Exception, source_language: str, target_language: str):
    """Maps a Google/LangChain exception to the matching TranspilerError subclass,
    logging at the appropriate severity before raising."""
    for exc_type, (mapped_exc, log_fn, log_prefix) in GOOGLE_ERROR_MAP.items():
        if isinstance(exc, exc_type):
            log_fn(f"{log_prefix} ({source_language}->{target_language}): {exc}")
            raise mapped_exc(extract_clean_message(exc, str(exc))) from exc
    raise LLMProviderError(str(exc)) from exc

def get_extension(language: str) -> str:
    return LANGUAGE_EXTENSIONS.get(language.lower(), "txt")


def get_start_marker(language: str) -> str | None:
    return LANGUAGE_START_MARKERS.get(language.lower())


def get_validator(language: str):
    """
    Returns an instance of BaseCodeValidator for the specified language,
    or None if the language is unsupported.
    """
    try:
        return ValidationFactory.get_validator(language)
    except ValueError:
        return None


def generate_hash(source_code: str, source_language: str, target_language: str) -> str:
    """
    Produces a deterministic fingerprint for a (source, source_language,
    target_language) combination. Same inputs always produce the same hash,
    used both for the in-memory cache key and the DB's source_hash column.
    """
    content = f"{source_language.strip().lower()}::{target_language.strip().lower()}::{source_code.strip()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()