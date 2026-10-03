from pathlib import Path
from fastapi.responses import PlainTextResponse
from fastapi import UploadFile, File, Form, Request, Query
from app.helpers import LANGUAGE_EXTENSIONS, MAX_CODE_BYTES, logger, exceptions as err
from app.services.transpiler import CodeTranspilerService

transpiler = CodeTranspilerService()
EXTENSION_TO_LANGUAGE = {ext: lang for lang, ext in LANGUAGE_EXTENSIONS.items()}

async def transpile_file(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    validate_syntax: bool = Form(True),
    use_cache: bool = Form(True),
):
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

    try:
        source_code = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        logger.error(f"Source file {file.filename} is not valid UTF-8 text.")
        raise err.InvalidFileEncodingError("Uploaded file is not valid UTF-8 text.")

    result = await transpiler.transpile(
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        base_name=base_name,
        validate_syntax=validate_syntax,
        use_cache=use_cache,
    )

    return {
        "success": True,
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
):
    body = await request.body()
    if len(body) > MAX_CODE_BYTES:
        raise err.TranspilerError("Code is too large.")

    try:
        source_code = body.decode("utf-8")
    except UnicodeDecodeError:
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

    result = await transpiler.transpile(
        source_code=source_code,
        source_language=source_language,
        target_language=target_language,
        base_name="snippet",
        validate_syntax=validate_syntax,
        use_cache=use_cache,
    )

    return PlainTextResponse(
        result["transpiled_code"],
        media_type="text/plain; charset=utf-8",
    )
