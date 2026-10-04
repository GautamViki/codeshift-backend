"""Curated evaluation cases for transpiler quality checks."""

EVAL_CASES = [
    {
        "id": "sum_two_numbers",
        "source_lang": "python",
        "target_lang": "go",
        "source_code": """
def add(a, b):
    return a + b
""",
        "input": [3, 5],
        "expected_output": 8,
        "kind": "behavior",
    },
    {
        "id": "filter_even_numbers",
        "source_lang": "python",
        "target_lang": "go",
        "source_code": """
def evens(nums):
    return [n for n in nums if n % 2 == 0]
""",
        "input": [[1, 2, 3, 4, 5, 6]],
        "expected_output": [2, 4, 6],
        "kind": "behavior",
    },
    {
        "id": "string_length",
        "source_lang": "python",
        "target_lang": "go",
        "source_code": """
def length(value):
    return len(value)
""",
        "input": ["hello"],
        "expected_output": 5,
        "kind": "behavior",
    },
]
