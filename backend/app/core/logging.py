import logging
import sys
import json

# Setup standard formatted logger for the application
logger = logging.getLogger("fifa_nexus_ai")
logger.setLevel(logging.INFO)

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
        # Add correlation ID if present in extra arguments
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id
        if hasattr(record, "trace_id"):
            log_record["trace_id"] = record.trace_id

        return json.dumps(log_record)

# Console Handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
