import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.transpilation import Transpilation


class TranspilationModelTests(unittest.TestCase):
    def test_created_at_column_is_timezone_aware(self):
        created_at_column = Transpilation.__table__.c.created_at

        self.assertTrue(created_at_column.type.timezone)


if __name__ == "__main__":
    unittest.main()
