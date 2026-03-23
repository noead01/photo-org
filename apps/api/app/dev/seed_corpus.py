from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.processing.ingest import ingest_directory
from app.services.ingest_queue_processor import process_pending_ingest_queue


@dataclass(frozen=True)
class SeedCorpusValidationReport:
    asset_count: int
    errors: list[str]


def resolve_seed_corpus_root() -> Path:
    return Path(__file__).resolve().parents[4] / "seed-corpus"


def load_seed_corpus_manifest(corpus_root: Path | None = None) -> dict[str, Any]:
    root = corpus_root or resolve_seed_corpus_root()
    manifest_path = root / "manifest.json"
    return json.loads(manifest_path.read_text())


def validate_seed_corpus(corpus_root: Path | None = None) -> SeedCorpusValidationReport:
    root = corpus_root or resolve_seed_corpus_root()
    manifest = load_seed_corpus_manifest(root)
    errors: list[str] = []
    paths_by_sha256: dict[str, list[str]] = {}

    assets = manifest.get("assets", [])
    if manifest.get("root") != "seed-corpus":
        errors.append("manifest root must be 'seed-corpus'")

    for asset in assets:
        asset_path = root.parent / asset["path"]
        if not asset_path.is_file():
            errors.append(f"missing file: {asset['path']}")
            continue
        digest = hashlib.sha256(asset_path.read_bytes()).hexdigest()
        paths_by_sha256.setdefault(digest, []).append(asset["path"])
        if not asset.get("license", {}).get("spdx"):
            errors.append(f"missing license spdx: {asset['asset_id']}")
        if not asset.get("license", {}).get("source_url"):
            errors.append(f"missing license source_url: {asset['asset_id']}")

    for digest, paths in paths_by_sha256.items():
        if len(paths) > 1:
            errors.append(
                f"duplicate sha256 {digest}: {', '.join(sorted(paths))}"
            )

    return SeedCorpusValidationReport(asset_count=len(assets), errors=errors)


def load_seed_corpus_into_database(
    *,
    database_url: str | None = None,
    queue_limit: int = 100,
) -> dict[str, int]:
    report = validate_seed_corpus()
    if report.errors:
        raise ValueError(f"seed corpus validation failed: {report.errors[0]}")

    ingest_result = ingest_directory(
        resolve_seed_corpus_root(),
        database_url=database_url,
        queue_commit_chunk_size=queue_limit,
    )
    processed = 0

    while True:
        batch = process_pending_ingest_queue(database_url, limit=queue_limit)
        processed += batch.processed
        if batch.processed == 0 and batch.retryable_errors == 0:
            break

    return {
        "scanned": ingest_result.scanned,
        "enqueued": ingest_result.enqueued,
        "processed": processed,
    }
