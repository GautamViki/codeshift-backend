import os
import sys
import unittest
from unittest.mock import patch

from app.validators.base_validator import ProcessRunner


class ProcessRunnerLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logs_subprocess_start_and_completion(self):
        command = f"{sys.executable} -c print('ok')"
        with patch("app.validators.base_validator.logger.info") as log_info:
            return_code, output = await ProcessRunner.run(
                sys.executable,
                "-c",
                "print('ok')",
                cwd=os.getcwd(),
            )

        self.assertEqual(return_code, 0)
        self.assertEqual(output.strip(), "ok")
        log_info.assert_any_call("Starting subprocess: %s", command)
        self.assertTrue(
            any(
                call.args[0] == "Subprocess completed: %s | exit_code=%s | duration_ms=%.2f"
                and call.args[1:3] == (command, 0)
                for call in log_info.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
