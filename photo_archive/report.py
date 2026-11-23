import html
from pathlib import Path

from photo_archive.analysis import ArchiveAnalysis
from photo_archive.models import PhotoMatch


class HtmlReport:

    def generate(self, analysis: ArchiveAnalysis, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)

        stats = analysis.statistics
        counts = analysis.status_counts()
        albums = analysis.album_correspondence()
        duplicates = analysis.duplicate_favourites()

        content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Photo Archive Analysis</title>
<style>
body {{
    font-family: system-ui, sans-serif;
    margin: 30px auto;
    max-width: 1400px;
    padding: 0 20px;
    color: #222;
    background: #f7f7f7;
}}
h1, h2 {{ margin-top: 32px; }}
.cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
}}
.card {{
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 16px;
}}
.card strong {{
    display: block;
    font-size: 26px;
}}
section {{
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 18px;
    margin-top: 20px;
    overflow-x: auto;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 14px;
}}
th, td {{
    text-align: left;
    padding: 9px;
    border-bottom: 1px solid #ddd;
    vertical-align: top;
}}
th {{ background: #eee; }}
.exact {{ color: #16733a; }}
.visual {{ color: #1763a5; }}
.ambiguous {{ color: #a36a00; }}
.none {{ color: #a22; }}
.muted {{ color: #666; }}
input {{
    padding: 9px;
    width: min(100%, 400px);
    margin-bottom: 12px;
}}
code {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>

<h1>Photo Archive Analysis</h1>
<p class="muted">Read-only analysis. No archive files were modified.</p>

<h2>Archive overview</h2>
<div class="cards">
    {self._card("Original JPGs", stats.original_jpg_count)}
    {self._card("Original NEFs", stats.original_nef_count)}
    {self._card("XMP sidecars", stats.original_xmp_count)}
    {self._card("PP3 sidecars", stats.original_pp3_count)}
    {self._card("Favourite JPGs", stats.favourite_jpg_count)}
    {self._card("Exact matches", counts.get("Exact file match", 0))}
    {self._card("Visual matches", counts.get("Likely visual match", 0))}
    {self._card("Ambiguous", counts.get("Ambiguous", 0))}
    {self._card("Unmatched", counts.get("No match", 0))}
</div>

<section>
<h2>Favourite albums and original folders</h2>
<p>
    Counts below show how many photographs in each favourite album
    were matched to each original folder. This is inferred evidence,
    not a forced folder mapping.
</p>
{self._album_table(albums)}
</section>

<section>
<h2>Favourite photographs</h2>
<input id="filter" type="search"
       placeholder="Filter by album, filename or original path..."
       oninput="filterRows()">
{self._match_table(analysis.matches)}
</section>

<section>
<h2>Duplicate files in favourites</h2>
{self._duplicate_table(duplicates)}
</section>

<script>
function filterRows() {{
    const query = document.getElementById('filter').value.toLowerCase();

    document.querySelectorAll('#matches tbody tr').forEach(row => {{
        row.style.display = row.innerText.toLowerCase().includes(query)
            ? ''
            : 'none';
    }});
}}
</script>

</body>
</html>
"""

        output.write_text(content, encoding="utf-8")

    @staticmethod
    def _card(label: str, value: int) -> str:
        return (
            '<div class="card">'
            f'<span>{html.escape(label)}</span>'
            f'<strong>{value:,}</strong>'
            '</div>'
        )

    def _album_table(self, albums: dict) -> str:
        if not albums:
            return "<p>No album relationships could be inferred.</p>"

        rows = []

        for album, folders in sorted(albums.items()):
            for folder, count in sorted(
                    folders.items(),
                    key=lambda item: item[1],
                    reverse=True,
            ):
                rows.append(
                    "<tr>"
                    f"<td>{html.escape(album)}</td>"
                    f"<td><code>{html.escape(folder)}</code></td>"
                    f"<td>{count}</td>"
                    "</tr>"
                )

        return (
                "<table><thead><tr>"
                "<th>Favourite album</th>"
                "<th>Original folder</th>"
                "<th>Matched photos</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table>"
        )

    def _match_table(self, matches: list[PhotoMatch]) -> str:
        rows = []

        for match in matches:
            status_class = {
                "Exact file match": "exact",
                "Likely visual match": "visual",
                "Ambiguous": "ambiguous",
                "No match": "none",
            }[match.status.value]

            original_path = (
                match.original.relative_path
                if match.original else ""
            )

            distance = (
                str(match.hash_distance)
                if match.hash_distance is not None else ""
            )

            rows.append(
                "<tr>"
                f"<td>{html.escape(match.favourite.favourite_album or '')}</td>"
                f"<td>{html.escape(match.favourite.filename)}</td>"
                f'<td class="{status_class}">'
                f"{html.escape(match.status.value)}</td>"
                f"<td><code>{html.escape(original_path)}</code></td>"
                f"<td>{html.escape(distance)}</td>"
                f"<td>{html.escape(match.explanation)}</td>"
                "</tr>"
            )

        return (
                '<table id="matches">'
                "<thead><tr>"
                "<th>Favourite album</th>"
                "<th>Favourite file</th>"
                "<th>Status</th>"
                "<th>Original file</th>"
                "<th>pHash distance</th>"
                "<th>Explanation</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table>"
        )

    def _duplicate_table(self, duplicates: dict) -> str:
        if not duplicates:
            return "<p>No byte-identical duplicate JPGs found in favourites.</p>"

        rows = []

        for digest, photos in duplicates.items():
            for photo in photos:
                rows.append(
                    "<tr>"
                    f"<td><code>{html.escape(digest[:16])}</code></td>"
                    f"<td>{html.escape(photo.favourite_album or '')}</td>"
                    f"<td>{html.escape(photo.relative_path)}</td>"
                    "</tr>"
                )

        return (
                "<table><thead><tr>"
                "<th>SHA-256</th><th>Album</th><th>File</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table>"
        )