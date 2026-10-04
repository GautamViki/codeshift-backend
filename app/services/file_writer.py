from pathlib import Path

from app.helpers.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
GENERATED_DIR = BASE_DIR / "generated_code"


def save_generated_code(code: str, base_name: str, extension: str) -> str:
    logger.info("Preparing generated-code output directory")
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    filepath = GENERATED_DIR / f"{base_name}.{extension}"
    logger.info("Writing generated-code file | filename=%s", filepath.name)
    filepath.write_text(code, encoding="utf-8")

    relative = filepath.relative_to(PROJECT_ROOT)
    short_path = f"{PROJECT_ROOT.name}/{relative}"

    logger.info("Generated-code file saved | path=%s", short_path)
    return short_path
