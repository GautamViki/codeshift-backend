# app/validators/code_validator.py
import ast
import os
import re
import shutil
import tempfile
from typing import Set, Tuple

from app.validators.base_validator import BaseCodeValidator, ValidationResult


class GoValidator(BaseCodeValidator):
    """Encapsulates Go formatting, vetting, and unused import removal."""

    UNUSED_IMPORT_RE = re.compile(r'"([^"]+)" imported(?: as \w+)? and not used')

    async def validate(self, code: str, fix_imports: bool = True) -> ValidationResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "main.go")
            self._write_file(path, code)

            # 1. Formatting & Import Fixes via goimports/gofmt
            if fix_imports and shutil.which("goimports"):
                step, cmd = "Go Imports", ("goimports", "-w", "main.go")
            else:
                step, cmd = "Go Format", ("gofmt", "-w", "main.go")

            rc, out = await self.runner.run(*cmd, cwd=tmpdir)
            if rc != 0:
                return ValidationResult(
                    False, f"{step} Error: {self._clean_output(out, tmpdir)}", code
                )
            code = self._read_file(path)

            # 2. Vet loop with automated import stripping passes
            for attempt in range(self.max_fix_passes + 1):
                rc, out = await self.runner.run("go", "vet", "main.go", cwd=tmpdir)
                if rc == 0:
                    return ValidationResult(True, "Code passed Go compiler syntax checks.", code)

                if not fix_imports or attempt == self.max_fix_passes:
                    break

                fixed_code, changed = self._remove_unused_imports(code, out)
                if not changed:
                    break

                self._write_file(path, fixed_code)
                await self.runner.run("gofmt", "-w", "main.go", cwd=tmpdir)
                code = self._read_file(path)

            return ValidationResult(False, f"Go Vet Error: {self._clean_output(out, tmpdir)}", code)

    def _remove_unused_imports(self, code: str, vet_output: str) -> Tuple[str, bool]:
        unused = set(self.UNUSED_IMPORT_RE.findall(vet_output))
        if not unused:
            return code, False

        kept, changed = [], False
        for line in code.splitlines():
            match = re.fullmatch(r'\s*(?:import\s+)?(?:[\w.]+\s+)?"([^"]+)"\s*', line)
            if match and match.group(1) in unused:
                changed = True
                continue
            kept.append(line)
        return "\n".join(kept) + "\n", changed


class PythonValidator(BaseCodeValidator):
    """Encapsulates Python syntax checking, AST import cleaning, and formatting."""

    UNUSED_IMPORT_RE = re.compile(r"[`'\"]([a-zA-Z0-9_]+)[`'\"]\s+imported but unused")

    async def validate(self, code: str, fix_imports: bool = True) -> ValidationResult:
        # Step 0: Fast immediate AST check
        try:
            ast.parse(code, filename="main.py")
        except SyntaxError as parse_err:
            return ValidationResult(
                ok=False,
                message=f"Python Syntax Error: line {parse_err.lineno}: {parse_err.msg}",
                code=code,
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "main.py")
            self._write_file(path, code)

            # Step 1: Format
            if shutil.which("ruff"):
                await self.runner.run("ruff", "format", "main.py", cwd=tmpdir)
                code = self._read_file(path)
            elif shutil.which("black"):
                await self.runner.run("black", "-q", "main.py", cwd=tmpdir)
                code = self._read_file(path)

            # Step 2: Lint and Fix Passes
            for attempt in range(self.max_fix_passes + 1):
                if shutil.which("ruff"):
                    rc, out = await self.runner.run("ruff", "check", "main.py", cwd=tmpdir)
                else:
                    rc, out = await self.runner.run(
                        "python", "-m", "py_compile", "main.py", cwd=tmpdir
                    )

                if rc == 0:
                    return ValidationResult(
                        True, "Code passed Python syntax and lint checks.", code
                    )

                if not fix_imports or attempt == self.max_fix_passes:
                    break

                # Apply import fix
                changed = False
                if shutil.which("ruff"):
                    await self.runner.run(
                        "ruff", "check", "--select", "F401", "--fix", "main.py", cwd=tmpdir
                    )
                    new_code = self._read_file(path)
                    changed = new_code != code
                    code = new_code
                else:
                    unused = set(self.UNUSED_IMPORT_RE.findall(out))
                    code, changed = self._remove_unused_imports_ast(code, unused)
                    self._write_file(path, code)

                if not changed:
                    break

            return ValidationResult(
                False, f"Python Lint Error:\n{self._clean_output(out, tmpdir)}", code
            )

    def _remove_unused_imports_ast(self, code: str, unused_imports: Set[str]) -> Tuple[str, bool]:
        if not unused_imports:
            return code, False

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code, False

        class ImportCleaner(ast.NodeTransformer):
            def __init__(self):
                self.changed = False

            def visit_Import(self, node: ast.Import):
                names = [n for n in node.names if n.name not in unused_imports]
                if len(names) != len(node.names):
                    self.changed = True
                return ast.Import(names=names) if names else None

            def visit_ImportFrom(self, node: ast.ImportFrom):
                names = [n for n in node.names if (n.asname or n.name) not in unused_imports]
                if len(names) != len(node.names):
                    self.changed = True
                return (
                    ast.ImportFrom(module=node.module, names=names, level=node.level)
                    if names
                    else None
                )

        cleaner = ImportCleaner()
        new_tree = cleaner.visit(tree)
        if cleaner.changed:
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree), True
        return code, False


class ValidationFactory:
    """Factory pattern to instantiate appropriate validator based on target language."""

    _validators = {
        "go": GoValidator,
        "python": PythonValidator,
        "py": PythonValidator,
    }

    @classmethod
    def get_validator(cls, language: str) -> BaseCodeValidator:
        lang_key = language.lower().strip()
        validator_cls = cls._validators.get(lang_key)
        if not validator_cls:
            raise ValueError(f"Unsupported language validation: '{language}'")
        return validator_cls()
