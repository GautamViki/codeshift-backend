import asyncio
import os
import tempfile


async def validate_go_code(code: str) -> tuple[bool, str]:
    """Asynchronously validates Go syntax without blocking the event loop."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "main.go")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Non-blocking go fmt
        proc_fmt = await asyncio.create_subprocess_exec(
            "go", "fmt", file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr_fmt = await proc_fmt.communicate()
        if proc_fmt.returncode != 0:
            return False, f"Go Format Error: {stderr_fmt.decode('utf-8')}"

        # Non-blocking go vet
        proc_vet = await asyncio.create_subprocess_exec(
            "go", "vet", file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr_vet = await proc_vet.communicate()
        if proc_vet.returncode != 0:
            return False, f"Go Vet Error: {stderr_vet.decode('utf-8')}"

        return True, "Code passed Go compiler syntax checks."


# Alias for backward compatibility
validate_go_code_async = validate_go_code