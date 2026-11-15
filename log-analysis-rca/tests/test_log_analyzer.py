import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from log_analyzer import analyze_lines, normalize_message, parse_line  # noqa: E402


class ParseLineTests(unittest.TestCase):
    def test_parses_error_line(self):
        record = parse_line("2026-11-15 10:02:03 ERROR database Connection timeout")
        self.assertIsNotNone(record)
        self.assertEqual(record.level, "ERROR")
        self.assertEqual(record.message, "database Connection timeout")

    def test_normalizes_warning_and_fatal_levels(self):
        warning = parse_line("2026-11-15T10:02:03Z [WARNING] cache retry")
        fatal = parse_line("2026-11-15T10:02:04Z FATAL service stopped")
        self.assertEqual(warning.level, "WARN")
        self.assertEqual(fatal.level, "CRITICAL")

    def test_ignores_unrecognised_lines(self):
        self.assertIsNone(parse_line("Application started without a timestamp"))


class AnalysisTests(unittest.TestCase):
    def test_counts_levels_and_groups_repeated_errors(self):
        lines = [
            "2026-11-15 10:02:03 INFO service started",
            "2026-11-15 10:02:04 ERROR database Connection 504 timed out",
            "2026-11-15 10:02:05 ERROR database Connection 505 timed out",
            "not a structured log line",
        ]
        report = analyze_lines(lines)
        self.assertEqual(report["total_lines"], 4)
        self.assertEqual(report["parsed_lines"], 3)
        self.assertEqual(report["unparsed_lines"], 1)
        self.assertEqual(report["error_count"], 2)
        self.assertEqual(report["top_error_patterns"][0]["count"], 2)

    def test_requires_positive_top_n(self):
        with self.assertRaises(ValueError):
            analyze_lines([], top_n=0)

    def test_normalizes_numbers_case_and_whitespace(self):
        self.assertEqual(
            normalize_message("Connection 123   TIMED OUT"),
            "connection <n> timed out",
        )


if __name__ == "__main__":
    unittest.main()
