# app/services/transpiler.py
import asyncio
import inspect
import re
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from app.config import config
from app.eval.cases import EVAL_CASES
from app.eval.metrics import summarize
from app.eval.runner import EvalRunner
from app.helpers.cache import transpile_cache
from app.helpers.constants import (
    GEMINI_MODEL_NAME,
    GEMINI_TEMPERATURE,
    THINKING_BUDGET,
)
from app.helpers.exceptions import (
    CodeValidationError,
    EmptyLLMResponseError,
    FileWriteError,
    ValidationToolUnavailableError,
)
from app.helpers.logger import logger
from app.helpers.utils import (
    get_extension,
    get_start_marker,
    get_validator,
    handle_llm_error,
)
from app.services.file_writer import save_generated_code

MAX_REPAIR_ATTEMPTS = 2

# Messages produced by ProcessRunner (or similar) when the tool itself failed,
# not the code. Sending these to the LLM as "code errors" wastes calls.
TOOLING_FAILURE_MARKERS = ("timed out after",)


def extract_code(raw_text: str, target_language: str) -> str:
    """Cleans backslashes and extracts code, dropping markdown fences and any text around them."""
    text = str(raw_text).strip()

    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n").replace("\\t", "\t")

    # 1. Strip a leading fence first (e.g. ```go\n), so the code survives the next steps.
    text = re.sub(r"^```[\w+-]*[ \t]*\n", "", text)

    # 2. Skip any preamble before the language's start marker, if known.
    marker = get_start_marker(target_language)
    if marker:
        match = re.search(marker, text, flags=re.MULTILINE)
        if match:
            text = text[match.start() :]

    # 3. Anything left that starts a fence is the closing fence (and trailing chatter): cut it.
    text = re.sub(r"\n?```.*$", "", text, flags=re.DOTALL).strip()
    return text


def is_tooling_failure(message: str) -> bool:
    """True if the validation message describes an infrastructure problem, not a code problem."""
    lowered = message.lower()
    return any(marker in lowered for marker in TOOLING_FAILURE_MARKERS)


class CodeTranspilerService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            temperature=GEMINI_TEMPERATURE,
            api_key=config.GOOGLE_API_KEY,
            thinking_budget=THINKING_BUDGET,
        )

    def _get_prompt(self, source_language: str, target_language: str) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"You are an expert compiler engineer. Translate {source_language} code to idiomatic {target_language} code.\n"
                    "IMPORTANT RULES:\n"
                    f"1. Output ONLY {target_language} code — no markdown code blocks, no backticks.\n"
                    "2. Do NOT add introductory or concluding text.\n"
                    "3. Preserve the behavior and structure of the source exactly. Translate only what is present: "
                    "do NOT add input validation, type checks, extra error handling, logging, comments or new features.\n"
                    "4. If the source already has error handling, translate it into the target language's conventions "
                    "(for example, exceptions to returned errors).\n"
                    "5. Include only the imports the code actually uses.\n"
                    "6. The code must compile: no unused imports and no unused local variables "
                    "(assign intentionally ignored values to `_` where the language allows it).\n"
                    f"7. Use only the {target_language} standard library. Do not import third-party packages "
                    "unless the source code clearly depends on them.",
                ),
                ("user", "{code}"),
            ]
        )

    def _normalize_validation(self, outcome, original_code: str) -> tuple[bool, str, str]:
        """
        Normalizes validation outputs:
        - ValidationResult (OOP validator) -> returns (outcome.ok, outcome.message, outcome.code)
        - Tuple (legacy validator)         -> returns (is_valid, message, original_code)
        """
        if hasattr(outcome, "ok"):
            return outcome.ok, outcome.message, getattr(outcome, "code", original_code)
        is_valid, message = outcome
        return is_valid, message, original_code

    async def transpile(
        self,
        source_code: str,
        source_language: str,
        target_language: str,
        base_name: str | None = None,
        validate_syntax: bool = True,
        use_cache: bool = True,
        **kwargs,
    ) -> dict:
        """Asynchronously transpile code, utilizing cache and non-blocking I/O."""
        should_validate = kwargs.get("validate", validate_syntax)
        cache_key = transpile_cache.generate_key(source_code, source_language, target_language)
        logger.info(f"Transpiling {source_language} to {target_language}, cache key {cache_key}")
        if use_cache:
            cached_result = transpile_cache.get(cache_key)
            if cached_result:
                logger.info(
                    f"Cache HIT for {source_language} -> {target_language} (key: {cache_key[:8]})"
                )
                return {**cached_result, "cached": True}

        if not base_name:
            base_name = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")

        prompt = self._get_prompt(source_language, target_language)
        chain = prompt | self.llm

        try:
            response = await chain.ainvoke({"code": source_code})
        except ChatGoogleGenerativeAIError as e:
            handle_llm_error(e, source_language, target_language)

        content = self.extract_text_from_response(response)
        raw_output = content.strip() if content else ""

        if not raw_output:
            raise EmptyLLMResponseError()

        generated_code = extract_code(raw_output, target_language)
        if not generated_code:
            raise EmptyLLMResponseError(
                f"Model response did not contain any {target_language} code."
            )

        is_valid, message, repair_attempts = True, f"Validation skipped for {target_language}.", 0
        if should_validate:
            validator = get_validator(target_language)
            if validator:
                (
                    is_valid,
                    message,
                    generated_code,
                    repair_attempts,
                ) = await self._validate_with_repair(validator, generated_code, target_language)
                if not is_valid:
                    raise CodeValidationError(message, transpiled_code=generated_code)
            else:
                message = f"No validator configured for {target_language}; skipped."

        logger.info(
            f"{source_language} -> {target_language} finished "
            f"(validated={should_validate}, repair_attempts={repair_attempts})"
        )

        try:
            extension = get_extension(target_language)
            saved_path = str(save_generated_code(generated_code, base_name, extension))
        except OSError as e:
            logger.error(f"Failed to write generated file for base_name={base_name}: {e}")
            raise FileWriteError(f"Could not write generated file: {str(e)}") from e

        result = {
            # Failed validation raises CodeValidationError above, so reaching here means success.
            "success": True,
            "transpiled_code": generated_code,
            "validation_message": message,
            "repair_attempts": repair_attempts,
            "saved_path": saved_path,
            "cached": False,
        }

        if use_cache and is_valid:
            transpile_cache.set(cache_key, result)

        return result

    async def evaluate_cases(self, prompt_version: str = "v1", cases=None):
        """Run the curated evaluation suite against the current transpiler and return a summary."""
        tasks = cases or EVAL_CASES
        runner = EvalRunner(self, prompt_version)
        results = []
        for case in tasks:
            results.append(await runner.run_case(case))
        return summarize(results)

    def extract_text_from_response(self, response) -> str:
        content = getattr(response, "content", response)
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

    async def _run_validator(self, validator, code: str, target_language: str):
        """Invokes OOP BaseCodeValidator objects or legacy function-based validators."""
        try:
            # Polymorphic OOP Validator check (BaseCodeValidator instance)
            if hasattr(validator, "validate"):
                outcome = await validator.validate(code)
            # Legacy coroutine function check
            elif inspect.iscoroutinefunction(validator):
                outcome = await validator(code)
            # Legacy synchronous function check
            else:
                outcome = await asyncio.to_thread(validator, code)
        except FileNotFoundError as e:
            logger.error(f"Validation tooling missing for {target_language}: {e}")
            raise ValidationToolUnavailableError() from e
        except Exception as e:
            logger.error(f"Validator for {target_language} raised unexpectedly: {e}", exc_info=True)
            raise ValidationToolUnavailableError(
                f"{target_language} validation crashed unexpectedly: {str(e)}"
            ) from e

        is_valid, message, validated_code = self._normalize_validation(outcome, code)

        # A timeout is a tooling problem: the model can't fix it, so don't spend repair calls on it.
        if not is_valid and is_tooling_failure(message):
            logger.error(f"Validation tooling failure for {target_language}: {message}")
            raise ValidationToolUnavailableError(message)

        return is_valid, message, validated_code

    async def _repair_code(self, code: str, error: str, target_language: str) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert {target_language} engineer. The code below failed compiler validation.\n"
                    "RULES:\n"
                    "1. Return the COMPLETE corrected file.\n"
                    "2. Fix only what the error reports; do not change behavior.\n"
                    "3. Use only the {target_language} standard library; do not add third-party imports.\n"
                    "4. Output ONLY code, with no markdown code blocks and no explanations.",
                ),
                ("user", "Validation error:\n{error}\n\nCode:\n{code}"),
            ]
        )
        try:
            response = await (prompt | self.llm).ainvoke(
                {"target_language": target_language, "error": error, "code": code}
            )
        except ChatGoogleGenerativeAIError as e:
            handle_llm_error(e, target_language, target_language)

        text = self.extract_text_from_response(response)
        return extract_code(text.strip(), target_language) if text else ""

    async def _validate_with_repair(self, validator, code: str, target_language: str):
        """
        Validate, and if it fails, ask the model to repair using the validator's error.
        Returns (is_valid, message, code, repair_attempts).
        """
        is_valid, message, code = await self._run_validator(validator, code, target_language)
        repairs = 0

        for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
            if is_valid:
                break
            logger.warning(
                f"{target_language} validation failed "
                f"(repair {attempt}/{MAX_REPAIR_ATTEMPTS}): {message}"
            )
            repaired = await self._repair_code(code, message, target_language)
            if not repaired:
                break
            if repaired.strip() == code.strip():
                logger.warning(f"{target_language} repair returned unchanged code; stopping.")
                break
            repairs = attempt
            is_valid, message, code = await self._run_validator(
                validator, repaired, target_language
            )

        return is_valid, message, code, repairs
