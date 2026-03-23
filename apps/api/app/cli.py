from __future__ import annotations

import argparse
import importlib.util
from importlib import import_module
from pathlib import Path

from app.dev.seed_corpus import validate_seed_corpus
from app.migrations import upgrade_database
from app.processing.faces import OpenCvFaceDetector
from app.storage import resolve_database_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-org")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest photos into the configured database")
    ingest_parser.add_argument("root", help="Directory containing photos")
    ingest_parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Defaults to DATABASE_URL.",
    )
    ingest_parser.add_argument(
        "--faces",
        action="store_true",
        help="Run OpenCV face detection and store detections",
    )
    migrate_parser = subparsers.add_parser("migrate", help="Apply database migrations")
    migrate_parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Defaults to DATABASE_URL.",
    )

    seed_corpus_parser = subparsers.add_parser(
        "seed-corpus",
        help="Validate and load the checked-in seed corpus",
    )
    seed_corpus_subparsers = seed_corpus_parser.add_subparsers(
        dest="seed_corpus_command",
        required=True,
    )

    seed_corpus_subparsers.add_parser(
        "validate",
        help="Validate the checked-in seed corpus and manifest",
    )

    seed_corpus_load_parser = seed_corpus_subparsers.add_parser(
        "load",
        help="Migrate and load the checked-in seed corpus",
    )
    seed_corpus_load_parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Defaults to DATABASE_URL.",
    )
    return parser


def _load_queue_client():
    source_path = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "cli"
        / "cli"
        / "queue_client.py"
    )
    if source_path.is_file():
        spec = importlib.util.spec_from_file_location(
            "photoorg_cli_queue_client",
            source_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load queue client from {source_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return import_module("cli.queue_client")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        detector = OpenCvFaceDetector() if args.faces else None
        result = _load_queue_client().enqueue_directory(
            args.root,
            database_url=args.database_url,
            face_detector=detector,
        )
        database_url = resolve_database_url(args.database_url)
        print(f"database_url={database_url}")
        print(f"scanned={result.scanned}")
        print(f"enqueued={result.enqueued}")
        print(f"inserted={result.inserted}")
        print(f"updated={result.updated}")
        if result.errors:
            print(f"errors={len(result.errors)}")
            for error in result.errors:
                print(error)
            return 1
        return 0
    if args.command == "migrate":
        upgrade_database(args.database_url)
        print(f"database_url={resolve_database_url(args.database_url)}")
        print("migration=head")
        return 0
    if args.command == "seed-corpus":
        if args.seed_corpus_command == "validate":
            report = validate_seed_corpus()
            print(f"assets_validated={report.asset_count}")
            if report.errors:
                print(f"errors={len(report.errors)}")
                for error in report.errors:
                    print(error)
                return 1
            print("validation=ok")
            return 0
        if args.seed_corpus_command == "load":
            upgrade_database(args.database_url)
            result = _load_queue_client().load_seed_corpus_into_queue(database_url=args.database_url)
            print(f"database_url={resolve_database_url(args.database_url)}")
            print(f"scanned={result['scanned']}")
            print(f"enqueued={result['enqueued']}")
            print(f"processed={result['processed']}")
            return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
