from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from app.services.transpiler import CodeTranspilerService

app = FastAPI(
    title="Polyglot Refactor Engine",
    description="API for modernizing and transpiling Python and Go codebases."
)

transpiler = CodeTranspilerService()

class TranspileRequest(BaseModel):
    source_code: str = Field(..., examples=["def add(a: int, b: int) -> int:\n    return a + b"])
    source_language: str = Field("python", examples=["python"])
    target_language: str = Field("go", examples=["go"])

@app.get("/")
def read_root():
    return {"status": "running", "service": "Polyglot Refactor Engine"}

@app.post("/api/v1/transpile")
async def transpile_code(request: TranspileRequest):
    src = request.source_language.lower()
    tgt = request.target_language.lower()

    if src == "python" and tgt == "go":
        timestamp = datetime.now().strftime("transpiled_%Y%b%d_%Hh_%Mm_%Ss")
        result = transpiler.python_to_go(request.source_code, base_name=timestamp)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error") or result.get("validation_message"))
        return {
            "success": True,
            "filename": f"{timestamp}.go",
            "saved_path": result.get("saved_path"),
            "validation_message": result.get("validation_message")
        }
    else:
        raise HTTPException(status_code=400, detail=f"Translation from {src} to {tgt} is not supported yet.")



@app.post("/api/v1/transpile-file")
async def transpile_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files are accepted")

    base_name = Path(file.filename).stem  # "script.py" -> "script"
    source_bytes = await file.read()
    py_code = source_bytes.decode("utf-8")

    result = transpiler.python_to_go(py_code, base_name=base_name)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error") or result.get("validation_message"))

    return {
        "success": True,
        "filename": f"{base_name}.go",
        "saved_path": result.get("saved_path"),
        "validation_message": result.get("validation_message")
    }