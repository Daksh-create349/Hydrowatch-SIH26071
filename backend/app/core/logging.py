"""Structured logging configuration."""

import logging
import sys
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """Configure structured logging format for backend service."""
    level_name = (log_level or "INFO").upper()
    numeric_level = getattr(logging, level_name, logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%dT%H:%M:%S%z"

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logger = logging.getLogger("rainfall_backend")
    logger.setLevel(numeric_level)
    return logger
