import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any


@dataclass
class EvalCase:
    id: str
    source_lang: str
    target_lang: str
    source_code: str
    input: Any
    expected_output: Any
    kind: str = "behavior"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        return cls(
            id=data["id"],
            source_lang=data["source_lang"],
            target_lang=data["target_lang"],
            source_code=data["source_code"],
            input=data["input"],
            expected_output=data["expected_output"],
            kind=data.get("kind", "behavior"),
        )


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    prompt_version: str
    runtime_error: str | None = None
    actual_output: Any = None
    expected_output: Any = None
    validation_message: str | None = None


class EvalRunner:
    def __init__(self, transpiler, prompt_version: str):
        self.transpiler = transpiler
        self.prompt_version = prompt_version

    async def run_case(self, case: EvalCase | dict[str, Any]) -> EvalResult:
        if isinstance(case, dict):
            case = EvalCase.from_dict(case)

        try:
            result = await self.transpiler.transpile(
                source_code=case.source_code,
                source_language=case.source_lang,
                target_language=case.target_lang,
                base_name=f"eval_{case.id}",
                validate_syntax=True,
                use_cache=False,
            )
        except Exception as exc:
            return EvalResult(
                case_id=case.id,
                passed=False,
                prompt_version=self.prompt_version,
                runtime_error=str(exc),
                validation_message="transpile_failed",
            )

        code = result.get("transpiled_code", "")
        if not code:
            return EvalResult(
                case_id=case.id,
                passed=False,
                prompt_version=self.prompt_version,
                runtime_error="empty transpiled output",
                validation_message=result.get("validation_message"),
            )

        try:
            if case.target_lang == "go":
                actual = self._run_go_code(case, code)
            else:
                raise NotImplementedError(f"Eval execution not supported for {case.target_lang}")
        except Exception as exc:
            return EvalResult(
                case_id=case.id,
                passed=False,
                prompt_version=self.prompt_version,
                runtime_error=str(exc),
                validation_message=result.get("validation_message"),
                expected_output=case.expected_output,
            )

        passed = actual == case.expected_output
        return EvalResult(
            case_id=case.id,
            passed=passed,
            prompt_version=self.prompt_version,
            actual_output=actual,
            expected_output=case.expected_output,
            validation_message=result.get("validation_message"),
        )

    def _run_go_code(self, case: EvalCase, generated_code: str):
        function_name = self._extract_go_function_name(generated_code)
        if not function_name:
            raise RuntimeError("Could not detect Go function name for evaluation.")

        call_args = self._build_go_call_arguments(case.input)
        wrapper = self._wrap_go_main(function_name, call_args)

        final_code = generated_code.rstrip() + "\n" + wrapper
        if "fmt." in wrapper and '"fmt"' not in generated_code:
            final_code = final_code.replace("package main\n", "package main\nimport \"fmt\"\n", 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "main.go")
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(final_code)

            proc = subprocess.run(
                ["go", "run", "main.go"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr or proc.stdout)

            try:
                return json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                return proc.stdout.strip()

    @staticmethod
    def _extract_go_function_name(code: str) -> str | None:
        match = re.search(r"func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", code)
        return match.group(1) if match else None

    @staticmethod
    def _wrap_go_main(function_name: str, call_args: str) -> str:
        return f"\nfunc main() {{\n    fmt.Println({function_name}({call_args}))\n}}\n"

    @staticmethod
    def _build_go_call_arguments(input_value: Any) -> str:
        if isinstance(input_value, list):
            if not input_value:
                return "[]int{}"
            if len(input_value) == 1 and isinstance(input_value[0], list):
                return EvalRunner._format_go_value(input_value[0])
            return ", ".join(EvalRunner._format_go_value(v) for v in input_value)
        return EvalRunner._format_go_value(input_value)

    @staticmethod
    def _format_go_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "nil"
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(value)
        if isinstance(value, list):
            if not value:
                return "[]int{}"
            inner = ", ".join(EvalRunner._format_go_value(v) for v in value)
            first = value[0]
            if isinstance(first, (int, float, bool)):
                return "[]int{" + inner + "}"
            if isinstance(first, str):
                return "[]string{" + inner + "}"
            return "[]interface{}{" + inner + "}"
        return json.dumps(str(value))
