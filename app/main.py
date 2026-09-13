from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.transpiler import CodeTranspilerService
from app.exceptions import TranspilerError, UnsupportedLanguageError, InvalidPythonSyntaxError
from app.logger import logger

app = FastAPI(
    title="Polyglot Refactor Engine",
    description="API for modernizing and transpiling Python and Go codebases."
)

transpiler = CodeTranspilerService()


class TranspileRequest(BaseModel):
    source_code: str = Field(..., examples=["def add(a: int, b: int) -> int:\n    return a + b"])
    source_language: str = Field("python", examples=["python"])
    target_language: str = Field("go", examples=["go"])


import warnings

warnings.filterwarnings(
    "ignore",
    message="Model 'gemini-3.6-flash' uses fixed sampling defaults.*",
    category=UserWarning,
    module="langchain_google_genai.chat_models",
)


import logging

logging.getLogger("google_genai.models").setLevel(logging.ERROR)
logging.getLogger("google_genai").setLevel(logging.ERROR)  # catches other submodules too, as a safety net

# ---- Exception handlers (global, apply to every route) ----

@app.exception_handler(TranspilerError)
async def transpiler_exception_handler(request: Request, exc: TranspilerError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error_type": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
    )


# ---- Middleware ----

from starlette.responses import Response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)

    if response.status_code >= 400:
        # Consume the streaming body
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        try:
            body_text = body_bytes.decode("utf-8")
        except Exception:
            body_text = "<non-utf8 body>"

        logger.info(f"Response status: {response.status_code} for {request.url.path} | detail: {body_text}")

        # Rebuild the response since we just consumed its original iterator
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    logger.info(f"Response status: {response.status_code} for {request.url.path}")
    return response

# ---- Shared helper ----

def _run_transpile(py_code: str, base_name: str) -> dict:
    result = transpiler.python_to_go(py_code, base_name=base_name)
    return {
        "success": True,
        "filename": f"{base_name}.go",
        "saved_path": result.get("saved_path"),
        "validation_message": result.get("validation_message"),
    }


# ---- Routes ----

@app.get("/")
def read_root():
    return {"status": "running", "service": "Polyglot Refactor Engine"}


@app.post("/api/v1/transpile")
async def transpile_code(request: TranspileRequest):
    src = request.source_language.lower()
    tgt = request.target_language.lower()

    if src != "python" or tgt != "go":
        raise UnsupportedLanguageError(f"Translation from {src} to {tgt} is not supported yet.")

    timestamp = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")
    return _run_transpile(request.source_code, timestamp)


@app.post("/api/v1/transpile-file")
async def transpile_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise UnsupportedLanguageError("Only .py files are accepted")

    base_name = Path(file.filename).stem  # "script.py" -> "script"
    source_bytes = await file.read()

    try:
        py_code = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidPythonSyntaxError("Uploaded file is not valid UTF-8 text.")

    return _run_transpile(py_code, base_name)