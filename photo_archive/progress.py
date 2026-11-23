
from dataclasses import dataclass


@dataclass
class ProgressReporter:
    description: str
    total: int

    def __post_init__(self):
        self.current = 0
        self.last_reported_percent = -10

        self._report(0)

    def advance(self, amount: int = 1):
        self.current = min(self.current + amount, self.total)

        if self.total == 0:
            percent = 100
        else:
            percent = int(self.current * 100 / self.total)

        milestone = (percent // 10) * 10

        if milestone > self.last_reported_percent:
            self._report(milestone)

    def finish(self):
        if self.current < self.total:
            self.current = self.total

        if self.last_reported_percent < 100:
            self._report(100)

    def _report(self, percent: int):
        self.last_reported_percent = percent

        print(
            f"{self.description}: "
            f"{percent:3d}% "
            f"({self.current:,}/{self.total:,})",
            flush=True,
        )
