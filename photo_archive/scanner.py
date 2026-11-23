
import hashlib
import os
from pathlib import Path
from typing import Any

import imagehash
from PIL import Image, ExifTags

from .cache import CacheManager
from .models import Photo
from .progress import ProgressReporter


class ArchiveScanner:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg"}

    def __init__(self, cache: CacheManager | None = None):
        self.cache = cache

    def scan(
            self,
            root: str | Path,
            is_favourites: bool = False,
    ) -> list[Photo]:
        root = Path(root).resolve()

        if not root.is_dir():
            raise NotADirectoryError(f"Directory does not exist: {root}")

        scan_kind = "favourites" if is_favourites else "original"
        root_path = str(root)

        # Enumerate paths and obtain basic file information.
        # This does not open or decode the image files.
        files: list[tuple[Path, os.stat_result]] = []

        for directory, _, filenames in os.walk(root):
            for filename in filenames:
                path = Path(directory) / filename

                if path.suffix.lower() not in self.IMAGE_EXTENSIONS:
                    continue

                try:
                    files.append((path, path.stat()))
                except OSError as error:
                    print(f"Cannot inspect {path}: {error}")

        progress = ProgressReporter(
            f"Scanning {scan_kind}",
            len(files),
        )

        photos: list[Photo] = []
        seen_paths: set[str] = set()
        reused_count = 0
        analysed_count = 0

        try:
            for path, file_stat in files:
                relative_path = path.relative_to(root).as_posix()
                absolute_path = str(path.resolve())

                seen_paths.add(absolute_path)

                cached = None
                if self.cache is not None:
                    cached = self.cache.get(
                        scan_kind=scan_kind,
                        root_path=root_path,
                        file_path=absolute_path,
                        file_size=file_stat.st_size,
                        mtime_ns=file_stat.st_mtime_ns,
                    )

                if cached is not None:
                    sha256 = cached["sha256"]
                    perceptual_hash = cached["perceptual_hash"]
                    metadata = cached["metadata"]
                    reused_count += 1
                else:
                    sha256 = self._calculate_sha256(path)
                    perceptual_hash = self._calculate_perceptual_hash(path)
                    metadata = self._extract_metadata(path)
                    analysed_count += 1

                    if self.cache is not None:
                        self.cache.put(
                            scan_kind=scan_kind,
                            root_path=root_path,
                            file_path=absolute_path,
                            file_size=file_stat.st_size,
                            mtime_ns=file_stat.st_mtime_ns,
                            sha256=sha256,
                            perceptual_hash=perceptual_hash,
                            metadata=metadata,
                        )

                photo = self._create_photo(
                    root=root,
                    path=path,
                    relative_path=relative_path,
                    sha256=sha256,
                    perceptual_hash=perceptual_hash,
                    metadata=metadata,
                    is_favourites=is_favourites,
                )

                photos.append(photo)
                progress.advance()

            progress.finish()

        except Exception:
            # Do not delete cache entries if the scan did not complete.
            raise

        removed_count = 0
        if self.cache is not None:
            removed_count = self.cache.remove_missing(
                scan_kind=scan_kind,
                root_path=root_path,
                seen_paths=seen_paths,
            )

        print(
            f"{scan_kind.capitalize()} scan summary: "
            f"{reused_count:,} reused, "
            f"{analysed_count:,} analysed, "
            f"{removed_count:,} removed from cache",
            flush=True,
        )

        return photos

    @staticmethod
    def _calculate_sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _calculate_perceptual_hash(path: Path) -> str | None:
        try:
            with Image.open(path) as image:
                return str(imagehash.phash(image.convert("RGB")))
        except Exception as error:
            print(f"Could not calculate perceptual hash for {path}: {error}")
            return None

    @staticmethod
    def _extract_metadata(path: Path) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        try:
            with Image.open(path) as image:
                exif = image.getexif()

                for tag_id, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))

                    # Store JSON-compatible values.
                    if isinstance(value, bytes):
                        value = value.hex()
                    elif not isinstance(
                            value,
                            (str, int, float, bool, type(None)),
                    ):
                        value = str(value)

                    metadata[tag_name] = value

                # Camera-specific EXIF data is often stored in EXIF IFD.
                try:
                    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                    for tag_id, value in exif_ifd.items():
                        tag_name = ExifTags.TAGS.get(
                            tag_id,
                            str(tag_id),
                        )

                        if isinstance(value, bytes):
                            value = value.hex()
                        elif not isinstance(
                                value,
                                (str, int, float, bool, type(None)),
                        ):
                            value = str(value)

                        metadata[tag_name] = value
                except (AttributeError, KeyError, TypeError):
                    pass

        except Exception as error:
            print(f"Could not extract EXIF from {path}: {error}")

        return metadata

    @staticmethod
    def _create_photo(
            root: Path,
            path: Path,
            relative_path: str,
            sha256: str,
            perceptual_hash: str | None,
            metadata: dict[str, Any],
            is_favourites: bool,
    ) -> Photo:
        parts = Path(relative_path).parts

        # Original archive month is normally the first YYMM directory.
        month = (
            parts[0]
            if not is_favourites and parts
            else None
        )

        # For favourites, the first directory under the favourites root
        # is treated as the album name.
        favourite_album = (
            parts[0]
            if is_favourites and len(parts) > 1
            else None
        )

        # For originals, use the immediate parent directory as the
        # source-folder identifier.
        source_folder = (
            str(Path(relative_path).parent)
            if not is_favourites
            else None
        )

        return Photo(
            path=path,
            relative_path=relative_path,
            filename=path.name,
            extension=path.suffix.lower(),
            sha256=sha256,
            perceptual_hash=perceptual_hash,
            metadata=metadata,
            month=month,
            source_folder=source_folder,
            favourite_album=favourite_album,
        )


    @staticmethod
    def count_files(
            root: str | Path,
            extensions: set[str] | None = None,
    ) -> int:
        """Count files recursively, optionally filtering by extension."""

        root = Path(root)

        if not root.is_dir():
            return 0

        extensions = (
            {extension.lower() for extension in extensions}
            if extensions
            else None
        )

        count = 0

        for directory, _, filenames in os.walk(root):
            for filename in filenames:
                if (
                        extensions is None
                        or Path(filename).suffix.lower() in extensions
                ):
                    count += 1

        return count
