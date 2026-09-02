"""Prepare the styled ODS master and copy it into the installable package."""

from argparse import ArgumentParser
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.easyprent_accounting.ods_template import prepare_settlement_template_bytes


DEFAULT_TEMPLATE = PROJECT_ROOT / "templates" / "utility_settlement.ods"
PACKAGED_TEMPLATE = (
    PROJECT_ROOT
    / "src"
    / "easyprent_accounting"
    / "templates"
    / "utility_settlement.ods"
)


def main() -> None:
    parser = ArgumentParser(
        description="Insert settlement markers without changing the ODS layout."
    )
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="styled source ODS (default: templates/utility_settlement.ods)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help=(
            "optional additional prepared copy; the active checkout master "
            "is always synchronized"
        ),
    )
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"source template does not exist: {args.source}")
    prepared = prepare_settlement_template_bytes(args.source.read_bytes())
    output_paths = dict.fromkeys(
        (args.output.resolve(), DEFAULT_TEMPLATE.resolve(), PACKAGED_TEMPLATE.resolve())
    )
    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(prepared)
    print(f"Master-Vorlage: {DEFAULT_TEMPLATE}")
    if args.output.resolve() != DEFAULT_TEMPLATE.resolve():
        print(f"Zusätzliche Kopie: {args.output}")
    print(f"Installationskopie: {PACKAGED_TEMPLATE}")


if __name__ == "__main__":
    main()
