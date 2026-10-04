from pydantic import BaseModel, Field


class TranspileRequest(BaseModel):
    source_code: str = Field(..., examples=["def add(a: int, b: int) -> int:\n    return a + b"])
    source_language: str = Field("python", examples=["python"])
    target_language: str = Field("go", examples=["go"])
    validate_syntax: bool = Field(
        True, description="Whether to validate syntax via compiler tooling", examples=[True]
    )
    use_cache: bool = Field(
        True,
        description="Whether to return cached transpilation result if available",
        examples=[True],
    )
