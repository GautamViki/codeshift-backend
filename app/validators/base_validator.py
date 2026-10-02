import os
from abc import ABC, abstractmethod
from asyncio.subprocess import PIPE
from dataclasses import dataclass
import asyncio
from typing import Optional, Tuple


@dataclass
class ValidationResult:
    ok: bool
    message: str
    code: str


class ProcessRunner:
    """Encapsulates subprocess execution and timeouts."""

    @staticmethod
    async def run(*cmd: str, cwd: str, timeout: float = 30.0) -> tuple[int, str] | tuple[int | None, str]:
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, stdout=PIPE, stderr=PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return 124, f"{cmd[0]} timed out after {timeout:.0f}s"
        return proc.returncode, (stdout + stderr).decode("utf-8", errors="replace")


class BaseCodeValidator(ABC):
    """Abstract Base Class for language-specific validators."""

    def __init__(self, max_fix_passes: int = 2, process_runner: Optional[ProcessRunner] = None):
        self.max_fix_passes = max_fix_passes
        self.runner = process_runner or ProcessRunner()

    @abstractmethod
    async def validate(self, code: str, fix_imports: bool = True) -> ValidationResult:
        """Core validation method implemented by language subclasses."""
        pass

    def _clean_output(self, message: str, tmpdir: str) -> str:
        """Normalizes and strips path artifacts from compiler outputs."""
        message = message.replace(tmpdir + os.sep, "").replace(tmpdir, "")
        lines = [ln for ln in message.splitlines() if ln.strip() and not ln.startswith("#")]
        return "\n".join(lines)
