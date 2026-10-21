
import json
import os
import unittest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class TestPulseIQETL(unittest.TestCase):

    def test_summary_exists(self):
        path = os.path.join(BASE_DIR, "reports", "etl_summary.json")
        self.assertTrue(os.path.isfile(path))

    def test_all_tables_processed(self):
        path = os.path.join(BASE_DIR, "reports", "etl_summary.json")
        with open(path, encoding="utf-8") as f:
            summary = json.load(f)

        self.assertEqual(summary["tables_processed"], 29)
        self.assertEqual(len(summary["results"]), 29)

    def test_row_counts_balance(self):
        path = os.path.join(BASE_DIR, "reports", "etl_summary.json")
        with open(path, encoding="utf-8") as f:
            summary = json.load(f)

        self.assertEqual(
            summary["total_rows_in"],
            summary["total_rows_passed"] + summary["total_rows_rejected"]
        )

    def test_run_log_exists(self):
        path = os.path.join(BASE_DIR, "reports", "etl_run.log")
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
