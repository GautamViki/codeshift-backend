from pydantic import BaseModel, Field


class TranspileRequest(BaseModel):
    source_code: str = Field(..., examples=["def add(a: int, b: int) -> int:\n    return a + b"])
    source_language: str = Field("python", examples=["python"])
    target_language: str = Field("go", examples=["go"])