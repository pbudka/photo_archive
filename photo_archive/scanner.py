import hashlib
import re
from pathlib import Path

import imagehash
from PIL import ExifTags, Image

from photo_archive.models import Photo


IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
RAW_EXTENSIONS = {".nef"}


class ArchiveScanner:

    def scan_originals(self, root: Path) -> list[Photo]:
        photos = []

        if not root.is_dir():
            raise ValueError(f"Original archive does not exist: {root}")

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            month = self._find_month(path, root)

            photo = self._create_photo(path, root)

            photo.month = month
            photo.source_folder = str(path.parent.relative_to(root))

            photos.append(photo)

        return photos

    def scan_favourites(self, root: Path) -> list[Photo]:
        photos = []

        if not root.is_dir():
            raise ValueError(f"Favourites directory does not exist: {root}")

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            photo = self._create_photo(path, root)

            relative = path.relative_to(root)

            # The first directory below the favourites root is the album.
            # Files directly in the root belong to "(root)".
            photo.favourite_album = (
                relative.parts[0] if len(relative.parts) > 1 else "(root)"
            )

            photos.append(photo)

        return photos

    def _create_photo(self, path: Path, root: Path) -> Photo:
        relative_path = str(path.relative_to(root))

        return Photo(
            path=path,
            relative_path=relative_path,
            filename=path.name,
            extension=path.suffix.lower(),
            sha256=self._sha256(path),
            perceptual_hash=self._perceptual_hash(path),
            metadata=self._read_exif(path),
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _perceptual_hash(path: Path) -> str | None:
        try:
            with Image.open(path) as image:
                return str(imagehash.phash(image.convert("RGB")))
        except Exception:
            return None

    @staticmethod
    def _read_exif(path: Path) -> dict[str, str]:
        result = {}

        try:
            with Image.open(path) as image:
                exif = image.getexif()

                if not exif:
                    return result

                # Standard TIFF/EXIF tags.
                for tag_id, value in exif.items():
                    name = ExifTags.TAGS.get(tag_id, str(tag_id))

                    if value is not None:
                        result[name] = str(value)

                # DateTimeOriginal and other EXIF IFD fields.
                try:
                    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)

                    for tag_id, value in exif_ifd.items():
                        name = ExifTags.TAGS.get(tag_id, str(tag_id))

                        if value is not None:
                            result[name] = str(value)

                except (AttributeError, KeyError, TypeError):
                    pass

        except Exception:
            pass

        return result

    @staticmethod
    def _find_month(path: Path, root: Path) -> str | None:
        relative = path.relative_to(root)

        for part in relative.parts:
            if re.fullmatch(r"\d{4}", part):
                return part

        return None

    @staticmethod
    def count_files(root: Path, extensions: set[str]) -> int:
        return sum(
            1
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        )