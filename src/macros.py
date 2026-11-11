"""
Macro definitions, their persistence and the execution of their shell commands.

A macro consists of:

    command        executed on every buzzer press (required)
    start_command  executed when the macro becomes active on a connected buzzer (optional)
    stop_command   executed when the macro stops being active, e.g. on disconnect (optional)
"""

import json
import subprocess
from dataclasses import asdict, dataclass

from PyQt5.QtCore import QSettings

MACROS_KEY = "macros"
ACTIVE_INDEX_KEY = "active_index"


@dataclass
class Macro:
    name: str
    command: str = ""
    start_command: str = ""
    stop_command: str = ""


def execute(command: str) -> None:
    """Starts the shell command in the background without waiting for it to finish.

    Raises OSError if the command could not be started.
    """
    subprocess.Popen(command, shell=True)


def load_macros(settings: QSettings) -> tuple[list[Macro], int | None]:
    """Returns the stored macros and the index of the active one."""
    try:
        entries = json.loads(settings.value(MACROS_KEY, "[]", type=str))
        macros = [Macro(**entry) for entry in entries]
    except (ValueError, TypeError):
        macros = []

    active_index = settings.value(ACTIVE_INDEX_KEY, -1, type=int)
    if not 0 <= active_index < len(macros):
        active_index = None
    return macros, active_index


def save_macros(settings: QSettings, macros: list[Macro], active_index: int | None) -> None:
    settings.setValue(MACROS_KEY, json.dumps([asdict(macro) for macro in macros]))
    settings.setValue(ACTIVE_INDEX_KEY, -1 if active_index is None else active_index)
