from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SECRET_HINTS = ("key", "password", "token", "secret", "authorization")


def _redact_secrets(_logger: object, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for k in list(event_dict):
        if any(h in k.lower() for h in _SECRET_HINTS):
            event_dict[k] = "***redacted***"
    return event_dict


def configure_logging(env: str, level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if env == "local":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "recruiter_agent") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
