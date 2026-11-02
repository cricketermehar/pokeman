"""
test_credential_store.py
========================
Unit tests for credential_store — loading, validation, edge cases.
Tests verify that passwords are NOT included in any log output.
"""

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from credential_store import load_credentials, mask_password


class TestLoadCredentials(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.accounts_file = Path(self.tmpdir.name) / "accounts.txt"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, content: str) -> None:
        self.accounts_file.write_text(content, encoding="utf-8")

    def test_basic_load(self):
        self._write("trainer01:P@ssw0rd1\ntrainer02:P@ssw0rd2\n")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 2)
        self.assertEqual(creds[0], ("trainer01", "P@ssw0rd1"))
        self.assertEqual(creds[1], ("trainer02", "P@ssw0rd2"))

    def test_skips_comments(self):
        self._write("# comment\ntrainer01:P@ssw0rd1\n# another\n")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 1)

    def test_skips_blank_lines(self):
        self._write("\n\ntrainer01:P@ssw0rd1\n\n")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 1)

    def test_password_with_colon(self):
        """Password may contain colons — only first colon is delimiter."""
        self._write("trainer01:pass:with:colons\n")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(creds[0], ("trainer01", "pass:with:colons"))

    def test_invalid_username_skipped(self):
        """Username with invalid characters is skipped with a warning."""
        self._write("bad-user!:P@ssw0rd1\n")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 0)

    def test_username_too_short_skipped(self):
        self._write("abc:P@ssw0rd1\n")  # 3 chars, min is 6
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 0)

    def test_password_too_short_skipped(self):
        self._write("trainer01:short\n")  # 5 chars, min is 8
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 0)

    def test_missing_delimiter_skipped(self):
        self._write("trainer01\n")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(len(creds), 0)

    def test_file_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_credentials(Path("/nonexistent/accounts.txt"))

    def test_empty_file_returns_empty_list(self):
        self._write("")
        creds = load_credentials(self.accounts_file)
        self.assertEqual(creds, [])

    def test_password_not_in_log_output(self):
        """Critical: passwords must not appear in any log message."""
        self._write("trainer01:UltraSecret99!\n")
        log_records = []

        class Capture(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        handler = Capture()
        logging.getLogger().addHandler(handler)
        try:
            load_credentials(self.accounts_file)
        finally:
            logging.getLogger().removeHandler(handler)

        for msg in log_records:
            self.assertNotIn("UltraSecret99!", msg,
                             f"Password found in log message: {msg}")


class TestMaskPassword(unittest.TestCase):

    def test_mask_shows_length(self):
        result = mask_password("MyS3cur3P@ss!")
        self.assertIn("13", result)  # 13 characters
        self.assertNotIn("MyS3cur3P@ss!", result)

    def test_mask_empty_string(self):
        result = mask_password("")
        self.assertIn("0", result)


if __name__ == "__main__":
    unittest.main()
