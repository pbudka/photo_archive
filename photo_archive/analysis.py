from collections import Counter, defaultdict
from pathlib import Path

from photo_archive.models import (
    ArchiveStatistics,
    MatchStatus,
    Photo,
    PhotoMatch,
)
from photo_archive.scanner import ArchiveScanner


class ArchiveAnalysis:

    def __init__(
            self,
            originals: list[Photo],
            favourites: list[Photo],
            matches: list[PhotoMatch],
            statistics: ArchiveStatistics,
    ):
        self.originals = originals
        self.favourites = favourites
        self.matches = matches
        self.statistics = statistics

    @classmethod
    def create(
            cls,
            original_root: Path,
            favourites_root: Path,
            originals: list[Photo],
            favourites: list[Photo],
            matches: list[PhotoMatch],
    ) -> "ArchiveAnalysis":

        statistics = ArchiveStatistics(
            original_jpg_count=len(originals),
            original_nef_count=ArchiveScanner.count_files(
                original_root, {".nef"}
            ),
            original_xmp_count=ArchiveScanner.count_files(
                original_root, {".xmp"}
            ),
            original_pp3_count=ArchiveScanner.count_files(
                original_root, {".pp3"}
            ),
            favourite_jpg_count=len(favourites),
        )

        return cls(
            originals=originals,
            favourites=favourites,
            matches=matches,
            statistics=statistics,
        )

    def album_correspondence(self) -> dict:
        """
        Map favourite albums to likely original source folders.

        Only exact and visual matches with a selected original contribute.
        Ambiguous matches do not contribute.
        """

        correspondence = defaultdict(Counter)

        for match in self.matches:
            if not match.original:
                continue

            album = match.favourite.favourite_album or "(root)"
            source = match.original.source_folder or "(unknown)"

            correspondence[album][source] += 1

        return {
            album: dict(folder_counts.most_common())
            for album, folder_counts in correspondence.items()
        }

    def duplicate_favourites(self) -> dict[str, list[Photo]]:
        by_hash = defaultdict(list)

        for photo in self.favourites:
            by_hash[photo.sha256].append(photo)

        return {
            digest: photos
            for digest, photos in by_hash.items()
            if len(photos) > 1
        }

    def status_counts(self) -> Counter:
        return Counter(match.status.value for match in self.matches)

    def matches_by_album(self) -> dict:
        result = defaultdict(list)

        for match in self.matches:
            album = match.favourite.favourite_album or "(root)"
            result[album].append(match)

        return dict(result)

    def unmatched_originals(self) -> list[Photo]:
        matched_hashes = {
            match.original.sha256
            for match in self.matches
            if match.original is not None
        }

        return [
            photo for photo in self.originals
            if photo.sha256 not in matched_hashes
        ]