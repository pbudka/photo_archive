import argparse
from pathlib import Path

from photo_archive.analysis import ArchiveAnalysis
from photo_archive.matcher import PhotoMatcher
from photo_archive.report import HtmlReport
from photo_archive.scanner import ArchiveScanner
from photo_archive.sequence import SequenceAnalyzer


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Analyse a photo archive and its favourites."
    )

    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Original archive root containing YYMM folders.",
    )

    parser.add_argument(
        "--favourites",
        required=True,
        type=Path,
        help="Favourites directory.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("photo_archive_report.html"),
        help="Output HTML report.",
    )

    return parser.parse_args()



def main():
    args = parse_arguments()

    scanner = ArchiveScanner()
    matcher = PhotoMatcher()

    print("\nPHOTO ARCHIVE ANALYSER")
    print("======================")

    print("\n[1/5] Scanning original archive")

    contents = scanner.count_archive_contents(args.source)

    print(f"      Folders: {contents['folders']:,}")
    print(f"      Files:   {contents['files']:,}")
    print(f"      JPGs:    {contents['jpgs']:,}")
    print(f"      NEFs:    {contents['nefs']:,}")

    originals = scanner.scan_originals(args.source)

    print("\n[2/5] Scanning favourites")

    favourites = scanner.scan_favourites(args.favourites)

    print("\n[3/5] Matching photographs")

    matches = matcher.match(favourites, originals)

    print("\n[4/5] Analysing archive")

    analysis = ArchiveAnalysis.create(
        original_root=args.source,
        favourites_root=args.favourites,
        originals=originals,
        favourites=favourites,
        matches=matches,
    )

    print("\n[5/5] Generating report")

    HtmlReport().generate(analysis, args.output)

    print("\nAnalysis completed.")
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()