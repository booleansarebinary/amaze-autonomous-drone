"""Injected clock interfaces; initial behavior intentionally incomplete for red tests."""
from typing import Protocol

class Clock(Protocol):
    def now_s(self) -> float: ...

class FakeClock:
    def __init__(self, initial_s: float = 0.0) -> None:
        self._now_s = initial_s

    def now_s(self) -> float:
        return self._now_s

    def advance_s(self, dt: float) -> None:
        pass

