from __future__ import annotations
from typing import Dict, List
from .models import Turn, UserPrefs

class MemoryStore:
    def __init__(self) -> None:
        # naive in-memory store keyed by session_id
        self._turns: Dict[str, List[Turn]] = {}
        self._prefs: Dict[str, UserPrefs] = {}

    def get_turns(self, session_id: str) -> List[Turn]:
        return list(self._turns.get(session_id, []))

    def add_turn(self, session_id: str, turn: Turn) -> None:
        self._turns.setdefault(session_id, []).append(turn)

    def set_prefs(self, session_id: str, prefs: UserPrefs) -> None:
        self._prefs[session_id] = prefs

    def get_prefs(self, session_id: str) -> UserPrefs:
        return self._prefs.get(session_id, UserPrefs())

# global singleton for demo
memory = MemoryStore()
