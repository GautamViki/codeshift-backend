from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from app.helpers.constants import LANGUAGE_EXTENSIONS
from app.services.transpiler import CodeTranspilerService
from app.helpers.exceptions import UnsupportedLanguageError, InvalidPythonSyntaxError
from app.schemas import TranspileRequest

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
    result = transpiler.transpile(request.source_code, src, tgt, base_name=timestamp)
    return {
        "success": True,
        "filename": f"{timestamp}.{LANGUAGE_EXTENSIONS[tgt]}",
        "saved_path": result.get("saved_path"),
        "validation_message": result.get("validation_message"),
    }

@router.post("/transpile-file")
async def transpile_file(
    file: UploadFile = File(...),
    target_language: str = Form(...),
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

    result = transpiler.transpile(source_code, source_language, target_language, base_name=base_name)

    return {
        "success": True,
        "filename": f"{base_name}.{LANGUAGE_EXTENSIONS[target_language]}",
        "saved_path": result.get("saved_path"),
        "validation_message": result.get("validation_message"),
    }