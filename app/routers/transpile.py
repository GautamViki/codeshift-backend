from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File

from app.services.transpiler import CodeTranspilerService
from app.helpers.exceptions import UnsupportedLanguageError, InvalidPythonSyntaxError
from app.schemas import TranspileRequest

router = APIRouter(prefix="/api/v1", tags=["transpile"])

transpiler = CodeTranspilerService()


def _run_transpile(py_code: str, base_name: str) -> dict:
    result = transpiler.python_to_go(py_code, base_name=base_name)
    return {
        "success": True,
        "filename": f"{base_name}.go",
        "saved_path": result.get("saved_path"),
        "validation_message": result.get("validation_message"),
    }


@router.post("/transpile")
async def transpile_code(request: TranspileRequest):
    src = request.source_language.lower()
    tgt = request.target_language.lower()

    if src != "python" or tgt != "go":
        raise UnsupportedLanguageError(f"Translation from {src} to {tgt} is not supported yet.")

    timestamp = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")
    return _run_transpile(request.source_code, timestamp)


@router.post("/transpile-file")
async def transpile_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise UnsupportedLanguageError("Only .py files are accepted")

    base_name = Path(file.filename).stem
    source_bytes = await file.read()

    try:
        py_code = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidPythonSyntaxError("Uploaded file is not valid UTF-8 text.")

    return _run_transpile(py_code, base_name)