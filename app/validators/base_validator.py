# app/validators/base_validator.py
import asyncio
import os
import time
from abc import ABC, abstractmethod
from asyncio.subprocess import PIPE
from dataclasses import dataclass
from typing import Optional

from app.helpers.logger import logger


@dataclass
class ValidationResult:
    ok: bool
    message: str
    code: str


class ProcessRunner:
    """Encapsulates subprocess execution and timeouts."""

    @staticmethod
    async def run(
        *cmd: str, cwd: str, timeout: float = 30.0
    ) -> tuple[int, str] | tuple[int | None, str]:
        command = " ".join(cmd)
        started_at = time.perf_counter()
        logger.info("Starting subprocess: %s", command)
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, stdout=PIPE, stderr=PIPE)
        except Exception as exc:
            logger.error(
                "Subprocess start exception | command=%s | type=%s | message=%s",
                command,
                type(exc).__name__,
                exc,
            )
            raise

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            duration_ms = (time.perf_counter() - started_at) * 1000
            message = f"{cmd[0]} timed out after {timeout:.0f}s"
            logger.error(
                "Subprocess timeout exception | command=%s | type=%s | message=%s | duration_ms=%.2f",
                command,
                type(exc).__name__,
                exc,
                duration_ms,
            )
            return 124, message
        except Exception as exc:
            logger.error(
                "Subprocess execution exception | command=%s | type=%s | message=%s",
                command,
                type(exc).__name__,
                exc,
            )
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "Subprocess completed: %s | exit_code=%s | duration_ms=%.2f",
            command,
            proc.returncode,
            duration_ms,
        )
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

    @staticmethod
    def _write_file(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _read_file(path: str) -> str:
        with open(path, encoding="utf-8") as f:
            return f.read()
