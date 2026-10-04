from fastapi import Depends, Query

from app.dependencies import get_current_user
from app.models.user import User
from app.services.transpiler import CodeTranspilerService


async def run_eval(
    prompt_version: str = Query("v1"),
    user: User = Depends(get_current_user),
):
    transpiler = CodeTranspilerService()
    summary = await transpiler.evaluate_cases(prompt_version=prompt_version)
    return {
        "prompt_version": summary.prompt_version,
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "pass_rate": summary.pass_rate,
        "failures": summary.failures,
    }
