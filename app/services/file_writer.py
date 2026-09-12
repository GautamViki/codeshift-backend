import uuid
from pathlib import Path

GENERATED_DIR = Path("generated_code")
GENERATED_DIR.mkdir(exist_ok=True)


def save_generated_go(code: str, base_name: str) -> Path:
    """
    Writes Go source to disk using the same base name as the input file.
    Re-running with the same input overwrites the previous output
    instead of creating a new file each time.
    """
    filepath = GENERATED_DIR / f"{base_name}.go"
    filepath.write_text(code, encoding="utf-8")
    return filepath