import json
import unittest
from unittest.mock import patch

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
    async def test_unhandled_exception_includes_request_id_header(self):
        handler = ExceptionHandler(FastAPI())
        request = make_request()
        request.state.request_id = "request-123"

        with patch("app.helpers.exceptions.logger.error"):
            response = await handler.unhandled_exception(request, RuntimeError("unexpected"))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["X-Request-ID"], "request-123")

    async def test_sqlalchemy_exception_uses_transpiler_error_response(self):
        handler = ExceptionHandler(FastAPI())
        exc = Exception("database down")

        with patch("app.helpers.exceptions.logger.error") as log_error:
            response = await handler.sqlalchemy_exception(make_request(), exc)

        self.assertEqual(response.status_code, DatabaseError.status_code)
        self.assertEqual(
            json.loads(response.body),
            DatabaseError("Database is temporarily unavailable. Please try again later.").to_dict(),
        )
        self.assertEqual(
            log_error.call_args.args[0],
            ("Database exception on %s %s from %s | type=%s | message=%s"),
        )
        self.assertEqual(log_error.call_args.args[4], "Exception")
        self.assertEqual(str(log_error.call_args.args[5]), "database down")


if __name__ == "__main__":
    unittest.main()
