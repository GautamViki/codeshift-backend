import asyncio
import os
import re
import shutil
import tempfile
from asyncio.subprocess import PIPE
from dataclasses import dataclass

MAX_FIX_PASSES = 2
UNUSED_IMPORT_RE = re.compile(r'"([^"]+)" imported(?: as \w+)? and not used')


@dataclass
class GoValidationResult:
    ok: bool
    message: str
    code: str  # cleaned code if processing succeeded, otherwise the input


async def _run(*cmd: str, cwd: str, timeout: float = 30.0) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, stdout=PIPE, stderr=PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, f"{cmd[0]} timed out after {timeout:.0f}s"
    return proc.returncode, (stdout + stderr).decode("utf-8", errors="replace")


def _clean(message: str, tmpdir: str) -> str:
    """Hide temp paths and go's '# command-line-arguments' noise."""
    message = message.replace(tmpdir + os.sep, "").replace(tmpdir, "")
    lines = [ln for ln in message.splitlines() if ln.strip() and not ln.startswith("#")]
    return "\n".join(lines)


def _remove_unused_imports(code: str, vet_output: str) -> tuple[str, bool]:
    unused = set(UNUSED_IMPORT_RE.findall(vet_output))
    if not unused:
        return code, False

    kept, changed = [], False
    for line in code.splitlines():
        m = re.fullmatch(r'\s*(?:import\s+)?(?:[\w.]+\s+)?"([^"]+)"\s*', line)
        if m and m.group(1) in unused:
            changed = True
            continue
        kept.append(line)
    return "\n".join(kept) + "\n", changed


async def validate_go_code_full(code: str, fix_imports: bool = True) -> GoValidationResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "main.go")

        def write(text: str) -> None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

        def read() -> str:
            with open(path, encoding="utf-8") as f:
                return f.read()

        write(code)

        # 1. Format (goimports also fixes imports; gofmt is the fallback)
        if fix_imports and shutil.which("goimports"):
            step, cmd = "Go Imports", ("goimports", "-w", "main.go")
        else:
            step, cmd = "Go Format", ("gofmt", "-w", "main.go")

        rc, out = await _run(*cmd, cwd=tmpdir)
        if rc != 0:
            return GoValidationResult(False, f"{step} Error: {_clean(out, tmpdir)}", code)
        code = read()

        # 2. Vet, removing unused imports between passes if needed
        for attempt in range(MAX_FIX_PASSES + 1):
            rc, out = await _run("go", "vet", "main.go", cwd=tmpdir)
            if rc == 0:
                return GoValidationResult(True, "Code passed Go compiler syntax checks.", code)

            if not fix_imports or attempt == MAX_FIX_PASSES:
                break
            fixed, changed = _remove_unused_imports(code, out)
            if not changed:
                break
            write(fixed)
            await _run("gofmt", "-w", "main.go", cwd=tmpdir)
            code = read()

        return GoValidationResult(False, f"Go Vet Error: {_clean(out, tmpdir)}", code)


# Backward-compatible wrapper (note: it drops the cleaned code)
async def validate_go_code(code: str) -> tuple[bool, str]:
    result = await validate_go_code_full(code)
    return result.ok, result.message


validate_go_code_async = validate_go_code