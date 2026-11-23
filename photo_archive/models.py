from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class MatchStatus(str, Enum):
    EXACT = "Exact file match"
    VISUAL = "Likely visual match"
    AMBIGUOUS = "Ambiguous"
    NO_MATCH = "No match"


@dataclass
class Photo:
    path: Path
    relative_path: str
    filename: str
    extension: str
    sha256: str
    perceptual_hash: str | None
    metadata: dict[str, str] = field(default_factory=dict)

    # Original archive information
    month: str | None = None
    source_folder: str | None = None

    # Favourites information
    favourite_album: str | None = None


@dataclass
class PhotoMatch:
    favourite: Photo
    status: MatchStatus
    original: Photo | None = None
    candidates: list[Photo] = field(default_factory=list)
    hash_distance: int | None = None
    explanation: str = ""


@dataclass
class ArchiveStatistics:
    original_jpg_count: int = 0
    original_nef_count: int = 0
    original_xmp_count: int = 0
    original_pp3_count: int = 0
    favourite_jpg_count: int = 0