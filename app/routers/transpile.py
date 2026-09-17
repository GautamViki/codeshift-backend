from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from starlette.responses import StreamingResponse

from app.helpers.constants import LANGUAGE_EXTENSIONS
from app.services.transpiler import CodeTranspilerService
from app.helpers.exceptions import UnsupportedLanguageError, InvalidPythonSyntaxError
from app.schemas import TranspileRequest
from app.helpers.logger import logger

router = APIRouter(prefix="/api/v1", tags=["transpile"])

transpiler = CodeTranspilerService()
# Reverse lookup: file extension -> language name
EXTENSION_TO_LANGUAGE = {ext: lang for lang, ext in LANGUAGE_EXTENSIONS.items()}


@router.post("/transpile")
async def transpile_code(request: TranspileRequest):
    src, tgt = request.source_language.lower(), request.target_language.lower()

    if src not in LANGUAGE_EXTENSIONS or tgt not in LANGUAGE_EXTENSIONS:
        raise UnsupportedLanguageError(f"Translation from {src} to {tgt} is not supported yet.")

    timestamp = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")
    result = await transpiler.transpile(
        source_code=request.source_code,
        source_language=src,
        target_language=tgt,
        base_name=timestamp,
        validate_syntax=request.validate_syntax,
        use_cache=request.use_cache,
    )

    return {
        "success": True,
        "filename": f"{timestamp}.{LANGUAGE_EXTENSIONS[tgt]}",
        "saved_path": result.get("saved_path"),
        "transpiled_code": result.get("transpiled_code"),
        "validation_message": result.get("validation_message"),
        "cached": result.get("cached", False),
    }


@router.post("/transpile-stream")
async def transpile_code_stream(request: TranspileRequest):
    """Streams generated code tokens in real-time for minimal time-to-first-byte (TTFB)."""
    src, tgt = request.source_language.lower(), request.target_language.lower()

    if src not in LANGUAGE_EXTENSIONS or tgt not in LANGUAGE_EXTENSIONS:
        raise UnsupportedLanguageError(f"Translation from {src} to {tgt} is not supported yet.")

    generator = transpiler.astream_transpile(request.source_code, src, tgt)

    # Pre-fetch the first chunk. If an initial error occurs (e.g. RateLimitExceededError,
    # AuthenticationError, etc.), it will raise HERE before the StreamingResponse starts,
    # allowing FastAPI's exception handlers to return a clean JSON error response (e.g. 429/401/500).
    try:
        first_chunk = await generator.__anext__()
    except StopAsyncIteration:
        first_chunk = None

    async def stream_wrapper():
        if first_chunk is not None:
            yield first_chunk
        try:
            async for chunk in generator:
                yield chunk
        except Exception as e:
            logger.error(f"Error mid-stream for {src}->{tgt}: {e}")
            yield f"\n\n[Streaming Error: {str(e)}]"

    return StreamingResponse(
        stream_wrapper(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/transpile-file")
async def transpile_file(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    validate_syntax: bool = Form(True),
    use_cache: bool = Form(True),
):
    ext = Path(file.filename).suffix.lstrip(".")
    source_language = EXTENSION_TO_LANGUAGE.get(ext)

    if source_language is None:
        raise UnsupportedLanguageError(f"Unsupported file type: .{ext}")

    target_language = target_language.lower()
    if target_language not in LANGUAGE_EXTENSIONS:
        raise UnsupportedLanguageError(f"Unsupported target language: {target_language}")

    base_name = Path(file.filename).stem
    source_bytes = await file.read()

    try:
        source_code = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidPythonSyntaxError("Uploaded file is not valid UTF-8 text.")

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
        "transpiled_code": result.get("transpiled_code"),
        "validation_message": result.get("validation_message"),
        "cached": result.get("cached", False),
    }