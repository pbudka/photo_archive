from collections import defaultdict

import imagehash

from photo_archive.models import MatchStatus, Photo, PhotoMatch


class PhotoMatcher:

    # Conservative initial thresholds. These can be tuned against your archive.
    MAX_VISUAL_DISTANCE = 8

    def match(
            self,
            favourites: list[Photo],
            originals: list[Photo],
    ) -> list[PhotoMatch]:

        exact_index = defaultdict(list)

        for original in originals:
            exact_index[original.sha256].append(original)

        results = []

        for favourite in favourites:
            exact_candidates = exact_index.get(favourite.sha256, [])

            if len(exact_candidates) == 1:
                results.append(
                    PhotoMatch(
                        favourite=favourite,
                        original=exact_candidates[0],
                        status=MatchStatus.EXACT,
                        candidates=exact_candidates,
                        hash_distance=0,
                        explanation="Identical SHA-256 file content.",
                    )
                )
                continue

            if len(exact_candidates) > 1:
                results.append(
                    PhotoMatch(
                        favourite=favourite,
                        status=MatchStatus.AMBIGUOUS,
                        candidates=exact_candidates,
                        explanation=(
                            "Identical file content exists in multiple "
                            "original archive locations."
                        ),
                    )
                )
                continue

            results.append(self._find_visual_match(favourite, originals))

        return results

    def _find_visual_match(
            self,
            favourite: Photo,
            originals: list[Photo],
    ) -> PhotoMatch:

        if not favourite.perceptual_hash:
            return PhotoMatch(
                favourite=favourite,
                status=MatchStatus.NO_MATCH,
                explanation="Could not calculate perceptual hash.",
            )

        favourite_hash = imagehash.hex_to_hash(
            favourite.perceptual_hash
        )

        scored = []

        for original in originals:
            if not original.perceptual_hash:
                continue

            original_hash = imagehash.hex_to_hash(
                original.perceptual_hash
            )

            distance = favourite_hash - original_hash

            scored.append((
                distance,
                self._metadata_score(favourite, original),
                original.filename == favourite.filename,
                original,
            ))

        if not scored:
            return PhotoMatch(
                favourite=favourite,
                status=MatchStatus.NO_MATCH,
                explanation="No comparable original images found.",
            )

        # Lowest distance first. Metadata and filename only break ties.
        scored.sort(
            key=lambda item: (
                item[0],
                -item[1],
                not item[2],
            )
        )

        best_distance = scored[0][0]

        if best_distance > self.MAX_VISUAL_DISTANCE:
            return PhotoMatch(
                favourite=favourite,
                status=MatchStatus.NO_MATCH,
                explanation=(
                    f"Closest visual candidate has distance "
                    f"{best_distance}; above the configured threshold."
                ),
            )

        best_candidates = [
            item for item in scored
            if item[0] == best_distance
        ]

        if len(best_candidates) > 1:
            return PhotoMatch(
                favourite=favourite,
                status=MatchStatus.AMBIGUOUS,
                candidates=[item[3] for item in best_candidates],
                hash_distance=best_distance,
                explanation=(
                    "Multiple originals have the same best perceptual "
                    "hash distance."
                ),
            )

        best = scored[0][3]

        return PhotoMatch(
            favourite=favourite,
            original=best,
            status=MatchStatus.VISUAL,
            candidates=[item[3] for item in scored[:3]],
            hash_distance=best_distance,
            explanation=(
                "Likely visual match. Verify manually if the distinction "
                "between similar photographs matters."
            ),
        )

    @staticmethod
    def _metadata_score(first: Photo, second: Photo) -> int:
        """
        Supporting evidence only.

        Filesystem timestamps are deliberately excluded.
        """

        fields = (
            "Make",
            "Model",
            "DateTimeOriginal",
            "SubSecTimeOriginal",
            "LensModel",
            "ExposureTime",
            "FNumber",
            "ISOSpeedRatings",
            "FocalLength",
        )

        score = 0

        for field in fields:
            first_value = first.metadata.get(field)
            second_value = second.metadata.get(field)

            if first_value and second_value and first_value == second_value:
                score += 1

        return score