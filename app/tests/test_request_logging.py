import logging
import re
import unittest

from fastapi import Request
from starlette.responses import JSONResponse, StreamingResponse

from app.helpers.logger import AppLogger


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


class RequestLoggingTests(unittest.IsolatedAsyncioTestCase):
    def test_app_logger_writes_to_file_without_console_handler(self):
        app_logger = AppLogger()

        self.assertTrue(
            any(isinstance(handler, logging.FileHandler) for handler in app_logger.logger.handlers)
        )
        self.assertFalse(
            any(
                isinstance(handler, logging.StreamHandler)
                and not isinstance(handler, logging.FileHandler)
                for handler in app_logger.logger.handlers
            )
        )

    async def test_request_id_is_logged_and_returned_in_response_header(self):
        app_logger = AppLogger()

        async def call_next(_request):
            app_logger.info("Handler step")
            return JSONResponse({"ok": True})

        with self.assertLogs(app_logger.logger, level="INFO") as captured:
            response = await app_logger.log_requests(make_request(), call_next)

        request_id = response.headers["X-Request-ID"]
        self.assertRegex(request_id, re.compile(r"^[0-9a-f]{12}$"))
        self.assertTrue(any(record.getMessage() == "Handler step" for record in captured.records))
        self.assertTrue(all(record.request_id == request_id for record in captured.records))

    async def test_each_request_gets_a_unique_request_id(self):
        app_logger = AppLogger()

        async def call_next(_request):
            return JSONResponse({"ok": True})

        first = await app_logger.log_requests(make_request(), call_next)
        second = await app_logger.log_requests(make_request(), call_next)

        self.assertNotEqual(first.headers["X-Request-ID"], second.headers["X-Request-ID"])

    async def test_error_response_keeps_request_id_header_and_body(self):
        app_logger = AppLogger()

        async def error_body():
            yield b'{"error":"bad request"}'

        async def call_next(_request):
            return StreamingResponse(error_body(), status_code=400)

        response = await app_logger.log_requests(make_request(), call_next)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.headers["X-Request-ID"])
        self.assertEqual(response.body, b'{"error":"bad request"}')


if __name__ == "__main__":
    unittest.main()
