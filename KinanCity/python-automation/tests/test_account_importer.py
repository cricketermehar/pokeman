"""
test_account_importer.py
========================
Unit tests for BulkAccountImporter:
- Multi-format parsing (colon, comma, RocketMap, tab)
- Duplicate detection
- PTC credential validation
- Batch partitioning
"""

import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from account_importer import BulkAccountImporter


class TestBulkAccountImporter(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name) / "accounts.txt"
        self.importer = BulkAccountImporter(self.target)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_various_formats(self):
        # RocketMap
        self.assertEqual(
            self.importer.parse_line("ptc,Trainer01,P@ssword123!"),
            ("Trainer01", "P@ssword123!", "RocketMap format"),
        )
        # Standard colon
        self.assertEqual(
            self.importer.parse_line("Trainer02:P@ssword456!"),
            ("Trainer02", "P@ssword456!", ""),
        )
        # Comma
        self.assertEqual(
            self.importer.parse_line("Trainer03,P@ssword789!"),
            ("Trainer03", "P@ssword789!", ""),
        )
        # Comments & blanks
        self.assertIsNone(self.importer.parse_line("# comment"))
        self.assertIsNone(self.importer.parse_line(""))

    def test_import_with_duplicates_and_invalids(self):
        source = Path(self.tmp.name) / "raw_accounts.csv"
        source.write_text(
            "ptc,TrainerValid1,P@ssword123!\n"
            "TrainerValid1:AnotherPass!\n"       # Duplicate username
            "bad,TooShort,P@ss!\n"              # Invalid format
            "TrainerValid2,P@ssword456!\n"
            "abc,ShortUser,P@ssword789!\n"      # Invalid username length
        )

        stats = self.importer.import_from_file(source)
        self.assertEqual(stats["imported_count"], 2)
        self.assertEqual(stats["duplicates_skipped"], 1)

        # Check target accounts.txt content
        lines = self.target.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("TrainerValid1:P@ssword123!", lines)
        self.assertIn("TrainerValid2:P@ssword456!", lines)

    def test_partition_into_batches(self):
        # Create target with 5 accounts
        self.target.write_text(
            "User01:Pass12345!\n"
            "User02:Pass12345!\n"
            "User03:Pass12345!\n"
            "User04:Pass12345!\n"
            "User05:Pass12345!\n"
        )
        batch_dir = Path(self.tmp.name) / "batches"
        batches = self.importer.partition_into_batches(batch_size=2, output_dir=batch_dir)
        self.assertEqual(len(batches), 3)  # 2 + 2 + 1
        self.assertTrue(batches[0].exists())


if __name__ == "__main__":
    unittest.main()
