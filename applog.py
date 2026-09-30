"""Logdatei fuer den Tray-Prozess.

Unter pythonw gibt es keine Konsole - ohne Logdatei verschwindet jeder
Fehler spurlos. Geschrieben wird nach
%LOCALAPPDATA%\\DualSenseCockpit\\logs\\dualsense.log, rotierend (3 x 1 MB).
Auch unbehandelte Ausnahmen in Threads landen dort.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path(__file__).parent))) \
    / "DualSenseCockpit" / "logs"
LOG_FILE = LOG_DIR / "dualsense.log"


def setup(level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return logging.getLogger("dualsense")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(threadName)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
    if sys.stderr is not None:          # python.exe: zusaetzlich Konsole
        root.addHandler(logging.StreamHandler())

    log = logging.getLogger("dualsense")

    def on_error(exc_type, exc, tb):
        log.critical("Unbehandelter Fehler", exc_info=(exc_type, exc, tb))

    def on_thread_error(args):
        log.critical("Unbehandelter Fehler im Thread %s",
                     args.thread.name if args.thread else "?",
                     exc_info=(args.exc_type, args.exc_value,
                               args.exc_traceback))

    sys.excepthook = on_error
    threading.excepthook = on_thread_error
    return log
