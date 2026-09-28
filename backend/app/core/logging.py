"""
Structured JSON logging and request context propagation for CivicPulse.

Implements Assignment Phase 8 requirements:
- JSON structured logging with timestamps, levels, logger name, and service name.
- Correlated request_id generation and propagation across contextvars.
- RequestIdMiddleware attaching X-Request-ID to request context and response headers.
- Request lifecycle logging with execution durations.
"""

import contextvars
import importlib.util
import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

HAS_PYTHON_JSON_LOGGER = importlib.util.find_spec("pythonjsonlogger") is not None


# Context variable holding the active request_id for the current task/coroutine
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id_ctx", default=None
)


def get_request_id() -> str | None:
    """Retrieve the active request_id from contextvar."""
    return request_id_ctx.get()


def set_request_id(req_id: str | None) -> None:
    """Set the active request_id in contextvar."""
    request_id_ctx.set(req_id)


class StructuredJsonFormatter(logging.Formatter):
    """
    Formatter outputting single-line structured JSON logs with correlated request_id.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "civicpulse",
        }

        # Automatically inject request_id if available in context
        req_id = get_request_id()
        if req_id:
            log_data["request_id"] = req_id

        # Merge standard extras
        for key, val in record.__dict__.items():
            if key not in [
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
            ]:
                log_data[key] = val

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def setup_logging(log_level: int = logging.INFO) -> None:
    """Configure the root logger with the StructuredJsonFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing stream handlers to prevent duplicate logging
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(handler)

    # Set Uvicorn loggers to use structured JSON as well
    for uvicorn_logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(uvicorn_logger_name)
        uv_logger.handlers = []
        uv_logger.addHandler(handler)
        uv_logger.propagate = False


logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that attaches and propagates an X-Request-ID header,
    manages contextvar correlation, and logs HTTP request lifecycle metrics.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract existing X-Request-ID or generate a new correlated identifier
        incoming_id = request.headers.get("X-Request-ID")
        req_id = (
            incoming_id.strip()
            if incoming_id and incoming_id.strip()
            else f"req-{uuid.uuid4().hex[:12]}"
        )

        # Propagate into contextvar and request state
        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            "HTTP request received",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "client_ip": client_ip,
            },
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_sec = time.perf_counter() - start_time
            duration_ms = round(duration_sec * 1000, 2)
            try:
                from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method, endpoint=request.url.path, status="500"
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=request.method, endpoint=request.url.path
                ).observe(duration_sec)
            except Exception:
                pass

            logger.error(
                "HTTP request failed with unhandled exception",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
                exc_info=True,
            )
            request_id_ctx.reset(token)
            raise exc

        duration_sec = time.perf_counter() - start_time
        duration_ms = round(duration_sec * 1000, 2)

        try:
            from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=request.url.path,
                status=str(response.status_code),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(duration_sec)
        except Exception:
            pass

        logger.info(
            "HTTP request completed",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        # Ensure X-Request-ID is attached to response headers
        response.headers["X-Request-ID"] = req_id
        request_id_ctx.reset(token)
        return response
