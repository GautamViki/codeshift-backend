import unittest

from app.eval.metrics import summarize
from app.eval.cases import EVAL_CASES


class DummyResult:
    def __init__(self, passed, case_id, prompt_version="v1"):
        self.passed = passed
        self.case_id = case_id
        self.prompt_version = prompt_version


class EvalMetricsTests(unittest.TestCase):
    def test_summarize_counts_pass_and_fail(self):
        results = [
            DummyResult(True, "case_1"),
            DummyResult(False, "case_2"),
            DummyResult(True, "case_3"),
        ]

        summary = summarize(results)

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.passed, 2)
        self.assertEqual(summary.failed, 1)
        self.assertAlmostEqual(summary.pass_rate, 2 / 3)
        self.assertEqual(summary.failures, ["case_2"])

    def test_eval_cases_have_required_fields(self):
        for case in EVAL_CASES:
            self.assertIn("id", case)
            self.assertIn("source_lang", case)
            self.assertIn("target_lang", case)
            self.assertIn("source_code", case)
            self.assertIn("input", case)
            self.assertIn("expected_output", case)


if __name__ == "__main__":
    unittest.main()
