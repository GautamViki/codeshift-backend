import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")

from app.handlers import auth_handler
from app.helpers.exceptions import DatabaseError
from app.services.auth import AuthService


class LoginHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_returns_success_message_and_bearer_token(self):
        with patch.object(
            auth_handler.auth_service, "login", new_callable=AsyncMock, return_value="test-token"
        ):
            response = await auth_handler.login(
                email="user@example.com",
                password="secretpassword123",
                db=object(),
            )

        self.assertEqual(
            response,
            {
                "success": True,
                "message": "Login successful.",
                "access_token": "test-token",
                "token_type": "bearer",
            },
        )

    async def test_login_translates_connection_refused_to_database_error(self):
        db = AsyncMock()
        connection_error = ConnectionRefusedError("database unavailable")
        db.execute.side_effect = connection_error

        with self.assertRaises(DatabaseError) as raised:
            await AuthService().login(db, "user@example.com", "secretpassword123")

        self.assertIs(raised.exception.__cause__, connection_error)


if __name__ == "__main__":
    unittest.main()
