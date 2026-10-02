"""Standard-library logging configuration."""

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once (INFO/WARNING/ERROR go to stderr)."""
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT)
    # SQL statements are only interesting when explicitly debugging.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
