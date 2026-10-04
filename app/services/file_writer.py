from pathlib import Path

from app.helpers.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
GENERATED_DIR = BASE_DIR / "generated_code"


def save_generated_code(code: str, base_name: str, extension: str) -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    filepath = GENERATED_DIR / f"{base_name}.{extension}"
    filepath.write_text(code, encoding="utf-8")

    relative = filepath.relative_to(PROJECT_ROOT)
    short_path = f"{PROJECT_ROOT.name}/{relative}"

    logger.info(f"Saved generated code to {short_path}")
    return short_path
