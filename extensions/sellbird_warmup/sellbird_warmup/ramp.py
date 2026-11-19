"""How many warmup emails a mailbox sends on a given day of its warmup."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Ramp:
    start: int = 5          # emails on day 1
    step: int = 3           # added each day
    cap: int = 40           # never more than this per day
    days: int = 14          # warmup length before cold sending is considered safe
    maintain: int = 12      # daily volume once warmed (keeps reputation alive)

    def day_number(self, started: date, today: date) -> int:
        return max(1, (today - started).days + 1)

    def quota(self, day: int) -> int:
        if day > self.days:
            return min(self.maintain, self.cap)
        return min(self.start + self.step * (day - 1), self.cap)

    def finished(self, day: int) -> bool:
        return day > self.days
