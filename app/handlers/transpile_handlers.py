from pathlib import Path
from typing import Any

from fastapi import Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.dependencies import get_current_user
from app.helpers import LANGUAGE_EXTENSIONS, MAX_CODE_BYTES, logger
from app.helpers import exceptions as err
from app.models.transpilation import Transpilation
from app.models.user import User
from app.services.history import TranspilationHistoryService
from app.services.transpiler import CodeTranspilerService

transpiler = CodeTranspilerService()
history_service = TranspilationHistoryService()
EXTENSION_TO_LANGUAGE = {ext: lang for lang, ext in LANGUAGE_EXTENSIONS.items()}


async def _save_transpilation_result(
    user_id: int,
    source_code: str,
    source_language: str,
    target_language: str,
    result: dict[str, Any],
) -> Transpilation:
    logger.info("Saving transpilation result to history")
    saved = await history_service.save(
        user_id=user_id,
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        transpiled_code=result["transpiled_code"],
        validated=result.get("success", False),
        validation_message=result.get("validation_message"),
    )
    logger.info("Transpilation result saved to history")
    return saved


async def transpile_file(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    validate_syntax: bool = Form(True),
    use_cache: bool = Form(True),
    current_user: User = Depends(get_current_user),
):
    logger.info("File transpilation request started")
    ext = Path(file.filename).suffix.lstrip(".")
    source_language = EXTENSION_TO_LANGUAGE.get(ext)

    if source_language is None:
        logger.error(f"Source language {source_language} not supported.")
        raise err.UnsupportedLanguageError(f"Unsupported file type: .{ext}")

    target_language = target_language.lower()
    if target_language not in LANGUAGE_EXTENSIONS:
        logger.error(f"Target language {target_language} not supported.")
        raise err.UnsupportedLanguageError(f"Unsupported target language: {target_language}")

    base_name = Path(file.filename).stem
    source_bytes = await file.read()
    logger.info("Uploaded file read | extension=%s | size_bytes=%s", ext, len(source_bytes))

    try:
        source_code = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        logger.error(
            "Uploaded source decode exception | filename=%s | type=%s | message=%s",
            file.filename,
            type(exc).__name__,
            exc,
        )
        raise err.InvalidFileEncodingError("Uploaded file is not valid UTF-8 text.")

    logger.info(
        "File input decoded; starting transpilation | source=%s | target=%s",
        source_language,
        target_language,
    )
    result = await transpiler.transpile(
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        base_name=base_name,
        validate_syntax=validate_syntax,
        use_cache=use_cache,
    )

    saved = await _save_transpilation_result(
        user_id=current_user.id,
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        result=result,
    )
    logger.info("File transpilation request completed")

    return {
        "success": True,
        "transpilation_id": saved.id,
        "filename": f"{base_name}.{LANGUAGE_EXTENSIONS[target_language]}",
        "saved_path": result.get("saved_path"),
        "validation_message": result.get("validation_message"),
        "cached": result.get("cached", False),
    }


async def transpile_raw(
    request: Request,
    source_language: str = Query(...),
    target_language: str = Query(...),
    validate_syntax: bool = Query(True),
    use_cache: bool = Query(True),
    current_user: User = Depends(get_current_user),
):
    logger.info("Raw-code transpilation request started")
    body = await request.body()
    logger.info("Raw-code request body received | size_bytes=%s", len(body))
    if len(body) > MAX_CODE_BYTES:
        raise err.TranspilerError("Code is too large.")

    try:
        source_code = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        logger.error(
            "Raw-code decode exception | type=%s | message=%s",
            type(exc).__name__,
            exc,
        )
        raise err.InvalidFileEncodingError("Request body is not valid UTF-8 text.")

    if not source_code.strip():
        raise err.TranspilerError("Request body is empty.")

    source_language = source_language.lower()
    target_language = target_language.lower()
    for lang in (source_language, target_language):
        if lang not in LANGUAGE_EXTENSIONS:
            raise err.UnsupportedLanguageError(
                f"Unsupported language: {lang}. Supported: {', '.join(LANGUAGE_EXTENSIONS)}"
            )

    logger.info(
        "Raw-code input validated; starting transpilation | source=%s | target=%s",
        source_language,
        target_language,
    )
    result = await transpiler.transpile(
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        base_name="snippet",
        validate_syntax=validate_syntax,
        use_cache=use_cache,
    )

    await _save_transpilation_result(
        user_id=current_user.id,
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        result=result,
    )
    logger.info("Raw-code transpilation request completed")

    return PlainTextResponse(
        result["transpiled_code"],
        media_type="text/plain; charset=utf-8",
    )
