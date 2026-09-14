"""Logging estructurado: cada línea de log es un objeto JSON (timestamp,
level, logger, message + campos extra) en vez de texto plano libre.

Necesario para que Loki/Grafana (docker-compose.yml, Semana 9 — promtail
scrapea stdout de los contenedores) puedan filtrar por campo (ej.
status_code, tenant_id) en vez de por regex sobre texto libre.
"""

from __future__ import annotations

import json
import logging
import sys

# Atributos que YA trae todo logging.LogRecord — lo que no está en esta
# lista es lo que el caller pasó vía logger.info(..., extra={...}).
_STANDARD_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # El middleware de app/main.py ya loguea una línea estructurada por
    # request (con tenant_id incluido) — dejar también el access log nativo
    # de uvicorn duplicaría esa línea en texto plano sin los campos extra.
    logging.getLogger("uvicorn.access").disabled = True
    for logger_name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = [handler]
        uv_logger.propagate = False
