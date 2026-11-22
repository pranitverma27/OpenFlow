"""
OpenFlow Diagnostic Logging Utility
Provides rotating, lightweight, persistent local logging stored in:
%APPDATA%/OpenFlow/logs/openflow.log (fallback ./user_data/logs/openflow.log)

Guarantees:
- Never logs microphone audio, raw speech buffers, or private transcribed text.
- Records application startup, lifecycle transitions, hardware device resolution,
  hotkey registration status, keyboard hook events, error stack traces, and cleanup.
"""
import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from utils_paths import get_user_data_dir

_LOGGER = None

def init_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("OpenFlow")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    candidates = [os.path.join(get_user_data_dir(), "logs"),
                  os.path.join(os.environ.get("TEMP", "."), "OpenFlow", "logs")]
    for log_dir in candidates:
        try:
            os.makedirs(log_dir, exist_ok=True)
            handler = RotatingFileHandler(os.path.join(log_dir, "openflow.log"),
                                          maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.log_dir = log_dir
            break
        except Exception:
            continue

    # Windowed (no-console) builds have sys.stdout/sys.stderr == None
    if sys.stdout is not None:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(console)

    def _excepthook(t, v, tb):
        logger.critical("Uncaught exception", exc_info=(t, v, tb))
    sys.excepthook = _excepthook
    try:
        import threading
        threading.excepthook = lambda a: logger.critical(
            f"Uncaught thread exception in {a.thread.name if a.thread else '?'}",
            exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    except Exception:
        pass

    _LOGGER = logger
    logger.info(f"Logger initialised; log_dir={getattr(logger, 'log_dir', 'NONE')} "
                f"exe={sys.executable} frozen={getattr(sys, 'frozen', False)} version=1.1.0")
    return _LOGGER

def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is None:
        return init_logger()
    return _LOGGER

def log_info(msg: str):
    get_logger().info(msg)

def log_warning(msg: str):
    get_logger().warning(msg)

def log_error(msg: str, exc: Exception = None):
    if exc:
        get_logger().error(f"{msg}: {exc}", exc_info=True)
    else:
        get_logger().error(msg)
