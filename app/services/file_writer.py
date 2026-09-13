from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated_code"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def save_generated_code(code: str, base_name: str, extension: str) -> Path:
    filepath = GENERATED_DIR / f"{base_name}.{extension}"
    filepath.write_text(code, encoding="utf-8")
    return filepath