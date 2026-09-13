from datetime import datetime
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from app.helpers.exceptions import (
    CodeValidationError, EmptyLLMResponseError,
    FileWriteError, ValidationToolUnavailableError
)
from app.config import config
from app.helpers.utils import handle_llm_error
from app.services.file_writer import save_generated_code
from app.helpers.utils import get_extension, get_start_marker, get_validator
from app.helpers.logger import logger
from app.helpers.constants import GEMINI_MODEL_NAME, GEMINI_TEMPERATURE


def extract_code(raw_text: str, target_language: str) -> str:
    """Cleans backslashes and extracts code starting from the language's marker, if known."""
    text = str(raw_text).strip()

    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n").replace("\\t", "\t")

    marker = get_start_marker(target_language)
    if marker:
        match = re.search(marker, text, flags=re.MULTILINE)
        if match:
            text = text[match.start():]

    text = re.sub(r'```.*$', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'^```\w*\n', '', text)
    return text


class CodeTranspilerService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            temperature=GEMINI_TEMPERATURE,
            api_key=config.GOOGLE_API_KEY,
        )

    def transpile(
        self,
        source_code: str,
        source_language: str,
        target_language: str,
        base_name: str | None = None,
    ) -> dict:
        response = {}
        if not base_name:
            base_name = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             f"You are an expert compiler engineer. Convert {source_language} code to idiomatic {target_language} code.\n"
             "IMPORTANT RULES:\n"
             f"1. Output ONLY {target_language} code — no markdown code blocks, no backticks.\n"
             "2. Do NOT add introductory or concluding text.\n"
             "3. Include explicit error handling and necessary imports, following that language's conventions."),
            ("user", "{code}")
        ])

        chain = prompt | self.llm

        try:
            response = chain.invoke({"code": source_code})
        except ChatGoogleGenerativeAIError as e:
            handle_llm_error(e, source_language, target_language)

        content = self.extract_text_from_response(response)
        raw_output = content.strip() if content else ""

        if not raw_output:
            raise EmptyLLMResponseError()

        generated_code = extract_code(raw_output, target_language)
        if not generated_code:
            raise EmptyLLMResponseError(f"Model response did not contain any {target_language} code.")

        validator = get_validator(target_language)
        is_valid, message = True, f"No validator configured for {target_language}; skipped."
        if validator:
            try:
                is_valid, message = validator(generated_code)
            except FileNotFoundError as e:
                logger.error(f"Validation tooling missing for {target_language}: {e}")
                raise ValidationToolUnavailableError() from e
            except Exception as e:
                logger.error(f"Validator for {target_language} raised unexpectedly: {e}", exc_info=True)
                raise ValidationToolUnavailableError(
                    f"{target_language} validation crashed unexpectedly: {str(e)}"
                ) from e

            if not is_valid:
                raise CodeValidationError(message)

        try:
            extension = get_extension(target_language)
            saved_path = str(save_generated_code(generated_code, base_name, extension))
        except OSError as e:
            logger.error(f"Failed to write generated file for base_name={base_name}: {e}")
            raise FileWriteError(f"Could not write generated file: {str(e)}") from e

        return {
            "success": is_valid,
            "transpiled_code": generated_code,
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
        original = exc.__cause__
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