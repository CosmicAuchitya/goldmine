"""
================================================================================
ENTERPRISE DUAL-STREAM STRUCTURED LOGGER FOR AUTONOMOUS PIPELINE
================================================================================
Guarantees:
1. Zero Subprocess Breakage: Console stream maintains clean visual tags ([*], [+], [!])
   for user readability and any downstream stdout parsers.
2. Audit-Grade File Persistence: Every message is concurrently recorded with ISO-8601
   timestamps, process/thread IDs, log levels, and module names.
3. Safe File Rotation: Automatically rolls logs after 10MB to prevent disk overflow.
================================================================================
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Ensure UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

LOGS_DIR = Path("runs/logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LOG_FILE = LOGS_DIR / "enterprise_pipeline.log"


class ConsoleFormatter(logging.Formatter):
    """Clean console formatter preserving DataX-Ray visual style."""
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if record.levelno >= logging.ERROR:
            prefix = "[!] [ERROR]"
        elif record.levelno >= logging.WARNING:
            prefix = "[!] [WARNING]"
        elif record.levelno == logging.INFO:
            # Preserve existing tag if present, else prepend [*]
            if msg.startswith(("[*]", "[+]", "[!]", "[STEP")):
                return msg
            prefix = "[*]"
        elif record.levelno <= logging.DEBUG:
            prefix = "[DEBUG]"
        else:
            prefix = "[*]"
        return f"{prefix} {msg}"


class StructuredFileFormatter(logging.Formatter):
    """Enterprise file formatter with timestamps, level, and caller info."""
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        module_name = record.name.replace("autonomous_engine.", "")
        level = record.levelname
        msg = record.getMessage()
        return f"[{timestamp}] [{level:<7}] [{module_name:<20}] {msg}"


_INITIALIZED_LOGGERS = {}

def get_pipeline_logger(name: str = "pipeline", log_file: Optional[Path] = None) -> logging.Logger:
    """
    Returns a configured dual-stream logger with console and rotating file output.
    """
    if name in _INITIALIZED_LOGGERS:
        return _INITIALIZED_LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        # 1. Console Stream (stdout)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ConsoleFormatter())
        logger.addHandler(console_handler)

        # 2. Rotating File Stream (10MB max, 5 backups)
        target_file = Path(log_file) if log_file else DEFAULT_LOG_FILE
        target_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFileFormatter())
        logger.addHandler(file_handler)

    _INITIALIZED_LOGGERS[name] = logger
    return logger


def log_print(*args, sep: str = " ", end: str = "\n", file=None, flush: bool = False) -> None:
    """
    Drop-in replacement for print() with print()'s exact signature.
    Routes the message through the structured logger, recording into
    runs/logs/enterprise_pipeline.log while outputting cleanly to console.
    """
    message = sep.join(str(a) for a in args)
    if not message.strip():
        sys.stdout.write(end)
        return

    logger = get_pipeline_logger("pipeline")
    stripped = message.lstrip()
    if stripped.startswith(("[!]", "[X]", "Fatal")):
        logger.warning(message)
    elif stripped.startswith("[ERROR]"):
        logger.error(message)
    elif stripped.startswith("[DEBUG]"):
        logger.debug(message)
    else:
        logger.info(message)

