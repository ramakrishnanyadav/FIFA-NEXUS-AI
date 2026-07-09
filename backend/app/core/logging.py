import logging
import sys
import json
import uuid
import time
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# ContextVar to propagate correlation ID across async task scopes
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

# Setup standard formatted logger for the application
logger = logging.getLogger("fifa_nexus_ai")
logger.setLevel(logging.INFO)

# Standard LogRecord fields to exclude from dynamic extra serialization
STANDARD_FIELDS = {
    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
    'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
    'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
    'processName', 'process', 'message'
}

# Structured JSON Formatter for production-grade logging
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno
        }
        
        # Inject correlation ID from ContextVar if active
        cid = correlation_id_ctx.get()
        if cid:
            log_record["correlation_id"] = cid
        elif hasattr(record, "correlation_id"):
            log_record["correlation_id"] = str(record.correlation_id)

        # Safely serialize custom extra variables passed in log call
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in STANDARD_FIELDS and not k.startswith('_')
        }
        log_record.update(extra_fields)

        return json.dumps(log_record, default=str)

# Console Handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Middleware to manage request-bound correlation IDs
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract from header or generate a new unique correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Set the ContextVar and attach to request state for down-stream access
        token = correlation_id_ctx.set(correlation_id)
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            client_ip = request.client.host if request.client else "unknown"
            
            # Log structured summary of request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} -> {status_code} ({latency_ms:.2f}ms)",
                extra={
                    "client_ip": client_ip,
                    "method": request.method,
                    "endpoint": request.url.path,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "correlation_id": correlation_id
                }
            )
            # Reset ContextVar to prevent context leaks across requests
            correlation_id_ctx.reset(token)
