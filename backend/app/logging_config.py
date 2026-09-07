"""
Structured logging.

Every log line is emitted as a single JSON object so it can be shipped
to any log aggregator (CloudWatch, ELK, Datadog...) without a custom
parser. We attach contextual fields (request_id, user, role, node)
via a ContextVar so nested async calls automatically get tagged.
"""
import contextvars
import json
import logging
import sys
import time
from typing import Any

request_context: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "request_context", default={}
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(request_context.get())
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    """Helper for structured 'event' style logs, e.g. agent transitions."""
    logger.info(message, extra={"extra_fields": fields})
