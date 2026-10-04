import json
import unittest

from fastapi import FastAPI, Request

from app.helpers.exceptions import DatabaseError, ExceptionHandler


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "root_path": "",
        }
    )


class ExceptionHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_sqlalchemy_exception_uses_transpiler_error_response(self):
        handler = ExceptionHandler(FastAPI())

        response = await handler.sqlalchemy_exception(make_request(), Exception("database down"))

        self.assertEqual(response.status_code, DatabaseError.status_code)
        self.assertEqual(
            json.loads(response.body),
            DatabaseError("Database is temporarily unavailable. Please try again later.").to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
