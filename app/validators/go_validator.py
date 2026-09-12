import subprocess
import tempfile
import os


def validate_go_code(code: str) -> tuple[bool, str]:
    """Saves code to a temp file and validates syntax via go fmt and go vet."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.go")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Run go fmt
        fmt_res = subprocess.run(["go", "fmt", file_path], capture_output=True, text=True)
        if fmt_res.returncode != 0:
            return False, f"Go Format Error: {fmt_res.stderr}"

        # Run go vet
        vet_res = subprocess.run(["go", "vet", file_path], capture_output=True, text=True)
        if vet_res.returncode != 0:
            return False, f"Go Vet Error: {vet_res.stderr}"

        return True, "Code passed Go compiler syntax checks."