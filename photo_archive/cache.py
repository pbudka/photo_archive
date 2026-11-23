
import json
import sqlite3
from pathlib import Path
from typing import Any


class CacheManager:
    """Stores extracted image metadata between analyser runs."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row

        self._create_tables()

    def _create_tables(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                                                     scan_kind TEXT NOT NULL,
                                                     root_path TEXT NOT NULL,
                                                     file_path TEXT NOT NULL,
                                                     file_size INTEGER NOT NULL,
                                                     mtime_ns INTEGER NOT NULL,
                                                     sha256 TEXT,
                                                     perceptual_hash TEXT,
                                                     metadata_json TEXT NOT NULL,
                                                     PRIMARY KEY (scan_kind, root_path, file_path)
                    )
                """
            )

            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_files_root
                    ON files (scan_kind, root_path)
                """
            )

    def get(
            self,
            scan_kind: str,
            root_path: str,
            file_path: str,
            file_size: int,
            mtime_ns: int,
    ) -> dict[str, Any] | None:
        """Return cached metadata if the file's stat information matches."""

        row = self.connection.execute(
            """
            SELECT sha256, perceptual_hash, metadata_json
            FROM files
            WHERE scan_kind = ?
              AND root_path = ?
              AND file_path = ?
              AND file_size = ?
              AND mtime_ns = ?
            """,
            (
                scan_kind,
                root_path,
                file_path,
                file_size,
                mtime_ns,
            ),
        ).fetchone()

        if row is None:
            return None

        return {
            "sha256": row["sha256"],
            "perceptual_hash": row["perceptual_hash"],
            "metadata": json.loads(row["metadata_json"]),
        }

    def put(
            self,
            scan_kind: str,
            root_path: str,
            file_path: str,
            file_size: int,
            mtime_ns: int,
            sha256: str,
            perceptual_hash: str | None,
            metadata: dict[str, Any],
    ) -> None:
        """Insert or update the cached metadata for a file."""

        metadata_json = json.dumps(metadata, ensure_ascii=False)

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO files (
                    scan_kind,
                    root_path,
                    file_path,
                    file_size,
                    mtime_ns,
                    sha256,
                    perceptual_hash,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (scan_kind, root_path, file_path)
                DO UPDATE SET
                    file_size = excluded.file_size,
                                           mtime_ns = excluded.mtime_ns,
                                           sha256 = excluded.sha256,
                                           perceptual_hash = excluded.perceptual_hash,
                                           metadata_json = excluded.metadata_json
                """,
                (
                    scan_kind,
                    root_path,
                    file_path,
                    file_size,
                    mtime_ns,
                    sha256,
                    perceptual_hash,
                    metadata_json,
                ),
            )

    def remove_missing(
            self,
            scan_kind: str,
            root_path: str,
            seen_paths: set[str],
    ) -> int:
        """Remove cached files that were not found during this scan."""

        rows = self.connection.execute(
            """
            SELECT file_path
            FROM files
            WHERE scan_kind = ? AND root_path = ?
            """,
            (scan_kind, root_path),
        ).fetchall()

        cached_paths = {row["file_path"] for row in rows}
        missing_paths = cached_paths - seen_paths

        if not missing_paths:
            return 0

        with self.connection:
            self.connection.executemany(
                """
                DELETE FROM files
                WHERE scan_kind = ?
                  AND root_path = ?
                  AND file_path = ?
                """,
                [
                    (scan_kind, root_path, path)
                    for path in missing_paths
                ],
            )

        return len(missing_paths)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
