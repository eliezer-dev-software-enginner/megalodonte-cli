"""Rich-based console formatting for CLI runtime diagnostics."""
from __future__ import annotations

import os
import sys
from typing import TextIO

from rich.console import Console
from rich.text import Text

COLORS = {"debug": "dim", "info": "cyan", "success": "green", "warning": "yellow", "error": "red"}


def log(scope: str, message: str, level: str = "info", stream: TextIO = sys.stdout) -> None:
    output = Text()
    output.append(f"[{scope}]", style="bold cyan")
    output.append(" ")
    output.append(message, style=COLORS.get(level, COLORS["info"]))
    Console(file=stream, force_terminal=False if "NO_COLOR" in os.environ else None,
            highlight=False, soft_wrap=True).print(output)


def live(message: str, level: str = "info", stream: TextIO = sys.stdout) -> None:
    log("live-reload", message, level, stream)


def native(message: str, level: str = "info", stream: TextIO = sys.stdout) -> None:
    log("native-host", message, level, stream)


def status_level(status: str) -> str:
    return {
        "APPLIED": "success",
        "SNAPSHOT": "success",
        "RESTART_REQUIRED": "warning",
        "REJECTED": "error",
        "FAILED": "error",
        "FATAL": "error",
    }.get(status, "info")
