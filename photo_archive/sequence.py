import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SequenceResult:
    folder: str
    prefix: str
    file_count: int
    missing_numbers: list[int]
    likely_rollover: bool

    @property
    def has_gaps(self) -> bool:
        return bool(self.missing_numbers)


class SequenceAnalyzer:

    PATTERN = re.compile(r"^(.*?)(\d{4})$", re.IGNORECASE)
    MODULUS = 10_000

    def analyse(self, root: Path) -> list[SequenceResult]:
        groups = defaultdict(list)

        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() != ".nef":
                continue

            match = self.PATTERN.match(path.stem)

            if not match:
                continue

            prefix, number_text = match.groups()
            number = int(number_text)

            key = (str(path.parent.relative_to(root)), prefix)
            groups[key].append(number)

        results = []

        for (folder, prefix), numbers in sorted(groups.items()):
            unique_numbers = sorted(set(numbers))

            rollover = (
                    len(unique_numbers) > 1
                    and unique_numbers[-1] >= 9000
                    and unique_numbers[0] <= 999
            )

            missing = self._find_missing(unique_numbers, rollover)

            results.append(
                SequenceResult(
                    folder=folder,
                    prefix=prefix,
                    file_count=len(numbers),
                    missing_numbers=missing,
                    likely_rollover=rollover,
                )
            )

        return results

    def _find_missing(
            self,
            numbers: list[int],
            rollover: bool,
    ) -> list[int]:

        missing = []

        for previous, current in zip(numbers, numbers[1:]):
            missing.extend(range(previous + 1, current))

        # With a likely rollover, do not treat the transition from
        # 9999 to 0000 as a gap.
        #
        # Missing values within the high and low ranges are still
        # reported above.
        return missing