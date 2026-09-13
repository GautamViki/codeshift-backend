from datetime import datetime
import libcst as cst
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from google.genai.errors import ClientError, ServerError
from langchain_google_genai.chat_models import GoogleRateLimitError, GoogleAuthenticationError, \
    GooglePermissionDeniedError, GoogleInvalidRequestError, GoogleModelNotFoundError, ChatGoogleGenerativeAIError

from app.exceptions import (
    InvalidPythonSyntaxError,
    RateLimitExceededError,
    InvalidApiKeyError,
    PermissionDeniedError,
    LLMProviderError,
    ProviderUnavailableError,
    GoValidationError,
    EmptyLLMResponseError, FileWriteError, GoToolingUnavailableError
)

_CODE_TO_EXCEPTION = {
    429: RateLimitExceededError,
    401: InvalidApiKeyError,
    403: PermissionDeniedError,
}

from app.config import config
from app.validators.go_validator import validate_go_code
from app.services.file_writer import save_generated_go
from app.logger import logger

def extract_go_code(raw_text: str) -> str:
    """Cleans backslashes and extracts raw Go code starting from `package`."""
    text = str(raw_text).strip()
    logger.info(f"Extracting Go code from {text}")
    # Safely replace literal escaped backslash sequences without using unicode_escape
    # Fixes single-line code blocks where \\n was returned instead of true newlines
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n").replace("\\t", "\t")

    # Locate the start of the Go package declaration
    package_match = re.search(r'\bpackage\s+\w+', text)
    if package_match:
        text = text[package_match.start():]

    # Strip trailing markdown code block closures (e.g., ```)
    text = re.sub(r'```.*$', '', text, flags=re.DOTALL).strip()
    return text


class CodeTranspilerService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0.0,
            api_key=config.GOOGLE_API_KEY,
        )

    def python_to_go(self, py_code: str, base_name: str | None = None) -> dict:
        if not base_name:
            base_name = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")

        # Step 1: Validate input Python syntax using CST
        try:
            cst.parse_module(py_code)
        except Exception as e:
            raise InvalidPythonSyntaxError(f"Invalid Python input syntax: {str(e)}")
        # Step 2: Prompt LLM with strict formatting rules
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert compiler engineer. Convert Python code to idiomatic Go code.\n"
                       "IMPORTANT RULES:\n"
                       "1. Output MUST start immediately with 'package main'.\n"
                       "2. Do NOT wrap the output in markdown code blocks or backticks.\n"
                       "3. Do NOT add introductory or concluding text.\n"
                       "4. Use standard Go double-quoted strings or raw backticks. Do NOT use single quotes for multi-character strings.\n"
                       "5. Include explicit error handling (if err != nil) and necessary imports."),
            ("user", "{code}")
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({"code": py_code})
        except GoogleRateLimitError as e:
            raise RateLimitExceededError(self._extract_clean_message(e, str(e)))
        except GoogleAuthenticationError as e:
            raise InvalidApiKeyError(self._extract_clean_message(e, str(e)))
        except GooglePermissionDeniedError as e:
            raise PermissionDeniedError(self._extract_clean_message(e, str(e)))
        except ChatGoogleGenerativeAIError as e:
            raise LLMProviderError(self._extract_clean_message(e, str(e)))

        content = self.extract_text_from_response(response)
        raw_output = content.strip() if content else ""

        if not raw_output:
            raise EmptyLLMResponseError()

        generated_go = extract_go_code(raw_output)
        if not generated_go:
            raise EmptyLLMResponseError("Model response did not contain any Go code.")

        try:
            is_valid, message = validate_go_code(generated_go)
        except FileNotFoundError:
            raise GoToolingUnavailableError()
        except Exception as e:
            raise GoToolingUnavailableError(f"Go validation crashed unexpectedly: {str(e)}")

        if not is_valid:
            raise GoValidationError(message)


        try:
            saved_path = str(save_generated_go(generated_go, base_name))
        except OSError as e:
            raise FileWriteError(f"Could not write generated file: {str(e)}")

        return {
            "success": is_valid,
            "transpiled_code": generated_go,
            "validation_message": message,
            "saved_path": saved_path,
        }

    def extract_text_from_response(self, response) -> str:
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "".join(parts)
        return str(content)

    def _extract_clean_message(self, exc: Exception, fallback: str) -> str:
        """Pulls the clean 'message' field out of the original Google API error,
        stripping off the nested quota/violation metadata."""
        original = exc.__cause__  # the underlying google.genai.errors.ClientError
        if original is not None and hasattr(original, "details"):
            try:
                details = original.details
                if isinstance(details, dict):
                    msg = details.get("error", {}).get("message")
                    if msg:
                        return msg.split("\n")[0].strip()
            except Exception:
                pass
        return fallback
