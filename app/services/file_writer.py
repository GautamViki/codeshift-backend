from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated_code"


def save_generated_code(code: str, base_name: str, extension: str) -> Path:
    # Ensure directory exists on the mounted filesystem before writing
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    filepath = GENERATED_DIR / f"{base_name}.{extension}"
    filepath.write_text(code, encoding="utf-8")
    return filepath