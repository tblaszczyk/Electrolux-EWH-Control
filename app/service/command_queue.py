"""
service/command_queue.py
Thread-safe kolejka komend API → Control Engine.

Strategia:
  SET_*    → last-write-wins (nadpisuje poprzednie tej samej klasy)
  RELOAD_* → kolejkowane normalnie (wszystkie wykonane)
"""

import threading
import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

log = logging.getLogger("boiler.queue")

# ══════════════════════════════════════════════════════════════
# TYPY KOMEND
# ══════════════════════════════════════════════════════════════

LAST_WRITE_WINS = {
    "SET_MANUAL",
    "SET_AUTO",
    "SET_IDLE_MODE",
}

QUEUE_ALL = {
    "RELOAD_SCHEDULE",
}


@dataclass
class Command:
    type: str                        # np. "SET_MANUAL"
    payload: dict = field(default_factory=dict)
    ts: datetime = field(default_factory=datetime.now)
    username: str = "system"

    def __repr__(self):
        return f"Command({self.type}, {self.payload}, by={self.username})"


# ══════════════════════════════════════════════════════════════
# QUEUE
# ══════════════════════════════════════════════════════════════

class CommandQueue:
    """
    Kolejka komend z dwoma trybami przetwarzania:
    - SET_*    → trzyma tylko ostatnią komendę danego typu (last-write-wins)
    - RELOAD_* → przechowuje wszystkie w FIFO
    """

    def __init__(self):
        self._lock     = threading.Lock()
        self._lw_cmds: dict[str, Command] = {}   # last-write-wins
        self._fifo:    list[Command]       = []   # queue-all

    def put(self, command: Command) -> None:
        """Wrzuć komendę do kolejki."""
        with self._lock:
            if command.type in LAST_WRITE_WINS:
                prev = self._lw_cmds.get(command.type)
                self._lw_cmds[command.type] = command
                if prev:
                    log.debug(f"Queue: nadpisano {command.type} (poprzednia: {prev.payload})")
                else:
                    log.debug(f"Queue: dodano {command}")
            elif command.type in QUEUE_ALL:
                self._fifo.append(command)
                log.debug(f"Queue: FIFO dodano {command}")
            else:
                log.warning(f"Queue: nieznany typ komendy '{command.type}' — odrzucono")

    def drain(self) -> list:
        """
        Opróżnij kolejkę — zwraca wszystkie oczekujące komendy.
        Wywołaj z Control Engine co pętlę (10s).
        """
        with self._lock:
            result = list(self._lw_cmds.values()) + self._fifo
            self._lw_cmds.clear()
            self._fifo.clear()
        if result:
            log.debug(f"Queue: drain → {len(result)} komend(y)")
        return result

    def pending_count(self) -> int:
        with self._lock:
            return len(self._lw_cmds) + len(self._fifo)

    def clear(self) -> None:
        with self._lock:
            self._lw_cmds.clear()
            self._fifo.clear()
        log.info("Queue: wyczyszczona")


# ── Fabryki komend ─────────────────────────────────────────────

def cmd_set_manual(
    temp: int,
    power_limit: int,
    username: str = "api"
) -> Command:
    return Command(
        type="SET_MANUAL",
        payload={"temp": temp, "power_limit": power_limit},
        username=username
    )


def cmd_set_auto(username: str = "api") -> Command:
    return Command(type="SET_AUTO", payload={}, username=username)


def cmd_set_idle_mode(mode: str, username: str = "api") -> Command:
    return Command(
        type="SET_IDLE_MODE",
        payload={"mode": mode},
        username=username
    )


def cmd_reload_schedule(username: str = "system") -> Command:
    return Command(type="RELOAD_SCHEDULE", payload={}, username=username)


# Singleton
queue = CommandQueue()


# Dodaj SET_SYSTEM_ENABLED do strategii last-write-wins
LAST_WRITE_WINS.add("SET_SYSTEM_ENABLED")


def cmd_set_system_enabled(enabled: bool, username: str = "api") -> Command:
    return Command(
        type="SET_SYSTEM_ENABLED",
        payload={"enabled": enabled},
        username=username
    )
