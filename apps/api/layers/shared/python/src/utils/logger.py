from __future__ import annotations
import json
import os
from datetime import datetime, timezone

class Logger:
    def __init__(self):
        self.level = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.is_local = os.environ.get("IS_LOCAL") == "true"
        self._order = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

    def _ok(self, level: str) -> bool:
        return self._order.get(level, 20) >= self._order.get(self.level, 20)

    def _fmt(self, level: str, message: str, data=None) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        if data is not None:
            payload["data"] = data
        return json.dumps(payload, default=str)

    def debug(self, message: str, data=None):
        if self._ok("DEBUG"):
            print(self._fmt("DEBUG", message, data))

    def info(self, message: str, data=None):
        if self._ok("INFO"):
            print(self._fmt("INFO", message, data))

    def warn(self, message: str, data=None):
        if self._ok("WARN"):
            print(self._fmt("WARN", message, data))

    def error(self, message: str, data=None):
        if self._ok("ERROR"):
            print(self._fmt("ERROR", message, data))

logger = Logger()
