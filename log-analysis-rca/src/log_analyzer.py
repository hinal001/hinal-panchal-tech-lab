"""Analyze timestamped application logs using only the Python standard library."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TIMESTAMP_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    r"(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<rest>.*)$"
)
LEVEL_RE = re.compile(r"\b(?P<level>TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b", re.I)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.I,
)
NUMBER_RE = re.compile(r"\b\d+\b")

LEVEL_ALIASES = {"WARNING": "WARN", "FATAL": "CRITICAL"}


@dataclass(frozen=True)
class LogRecord:
    timestamp: str
    level: str
    message: str


def parse_line(line: str) -> LogRecord | None:
    """Parse a timestamped line containing a recognised severity word."""
    match = TIMESTAMP_RE.match(line.strip())
    if not match:
        return None

    rest = match.group("rest")
    level_match = LEVEL_RE.search(rest)
    if not level_match:
        return None

    level = level_match.group("level").upper()
    level = LEVEL_ALIASES.get(level, level)
    message = rest[level_match.end():].strip(" \t:-[]")
    if not message:
        message = rest.strip()
    return LogRecord(match.group("timestamp"), level, message)


def normalize_message(message: str) -> str:
    """Reduce common changing identifiers so repeated errors can be grouped."""
    normalized = UUID_RE.sub("<uuid>", message)
    normalized = NUMBER_RE.sub("<n>", normalized)
    return re.sub(r"\s+", " ", normalized).strip().lower()


def analyze_lines(lines: Iterable[str], top_n: int = 10) -> dict:
    """Return a JSON-serialisable summary for an iterable of log lines."""
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    total_lines = 0
    records: list[LogRecord] = []
    for line in lines:
        total_lines += 1
        record = parse_line(line)
        if record is not None:
            records.append(record)

    level_counts = Counter(record.level for record in records)
    error_records = [r for r in records if r.level in {"ERROR", "CRITICAL"}]
    pattern_counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for record in error_records:
        pattern = normalize_message(record.message)
        pattern_counts[pattern] += 1
        examples.setdefault(pattern, record.message)

    top_patterns = [
        {"pattern": pattern, "count": count, "example": examples[pattern]}
        for pattern, count in pattern_counts.most_common(top_n)
    ]

    return {
        "total_lines": total_lines,
        "parsed_lines": len(records),
        "unparsed_lines": total_lines - len(records),
        "level_counts": dict(sorted(level_counts.items())),
        "error_count": len(error_records),
        "top_error_patterns": top_patterns,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarise timestamped application logs and repeated error patterns."
    )
    parser.add_argument("input", type=Path, help="Path to a UTF-8 text log file")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON report to this path")
    parser.add_argument("--top", type=int, default=10, help="Number of error patterns to include (default: 10)")
    args = parser.parse_args(argv)

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")

    try:
        with args.input.open("r", encoding="utf-8", errors="replace") as handle:
            report = analyze_lines(handle, top_n=args.top)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        try:
            args.output.write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"error writing report: {exc}", file=sys.stderr)
            return 1
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
