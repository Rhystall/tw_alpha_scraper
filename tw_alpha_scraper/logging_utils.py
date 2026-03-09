from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


SENSITIVE_PATTERNS = [
    re.compile(r"https://discord\.com/api/webhooks/[^\s]+"),
    re.compile(r"(auth_token=)[^;\s]+"),
    re.compile(r"(ct0=)[^;\s]+"),
    re.compile(r"(https?://)([^:@/\s]+):([^@/\s]+)@"),
]


def sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(lambda match: _replacement(match), sanitized)
    return sanitized


def _replacement(match: re.Match[str]) -> str:
    if match.lastindex and match.group(1):
        if len(match.groups()) >= 3:
            return f"{match.group(1)}[REDACTED]:[REDACTED]@"
        return f"{match.group(1)}[REDACTED]"
    return "[REDACTED]"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            record.msg = sanitize_text(str(record.msg))
            if record.args:
                record.args = tuple(sanitize_text(str(arg)) for arg in record.args)
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


def setup_logging(log_path: str) -> logging.Logger:
    logger = logging.getLogger("tw_alpha_scraper")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = RedactingFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
