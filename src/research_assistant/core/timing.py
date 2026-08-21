"""Lightweight stage timing for logs. Not a metrics platform."""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import TracebackType


@dataclass(frozen=True)
class Timing:
    name: str
    seconds: float

    @property
    def milliseconds(self) -> float:
        return self.seconds * 1000.0


class Timer:
    def __init__(self, name: str) -> None:
        self.name = name
        self._start = 0.0
        self.seconds = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.seconds = time.perf_counter() - self._start

    def result(self) -> Timing:
        return Timing(self.name, self.seconds)
