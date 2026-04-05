# Issue 126 Staged Ingest Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor watched-folder ingest so polling only discovers candidate files, downstream workers hash and analyze content in parallelizable stages, and persistence reuses extracted artifacts for duplicate SHA content without reopening originals for face detection.

**Architecture:** Keep source validation, watched-folder reconciliation, and ingest-run bookkeeping in the polling layer, but move file reading and media-derived work behind queued worker stages. Introduce an explicit candidate payload for discovery, a content-analysis payload keyed by SHA, and persistence logic that can reuse metadata, thumbnails, and face detections when the same content appears at multiple paths.

**Tech Stack:** Python, SQLAlchemy Core, pytest, existing ingest queue store and ingest-run bookkeeping, OpenCV face detection, Pillow thumbnail/metadata extraction

---

## File Map

**Create:**

- `apps/api/app/services/ingest_extraction_worker.py`
  Own the staged worker flow that reads a candidate file, computes SHA, short-circuits known-content analysis, runs metadata/thumbnail/face extraction when needed, and hands a complete payload to persistence.
- `apps/api/tests/test_ingest_extraction_worker.py`
  Cover hashing short-circuit behavior, new-content analysis, duplicate-content reuse, and stage-specific failure handling.

**Modify:**

- `apps/api/app/processing/ingest_polling.py`
  Replace inline `build_photo_record()` and thumbnail work in the polling loop with candidate enqueueing and preserve watched-folder bookkeeping.
- `apps/api/app/services/ingest_queue_processor.py`
  Split persistence from analysis, consume new payload types, and remove direct original-file face detection from persistence.
- `apps/api/app/processing/ingest_persistence.py`
  Add candidate payload builders, extracted payload serializers/parsers, and persistence helpers that can reuse derived artifacts by SHA.
- `apps/api/app/db/queue.py`
  Keep the queue API generic enough for multiple payload types and update tests only if payload routing needs a small helper.
- `apps/api/app/processing/ingest.py`
  Keep facade entrypoints stable while delegating polling to the new discovery behavior.

**Test:**

- `apps/api/tests/test_ingest_polling.py`
- `apps/api/tests/test_ingest_queue_processor.py`
- `apps/api/tests/test_ingest_persistence.py`
- `apps/api/tests/test_ingest.py`

### Task 1: Define The New Queue Payload Contracts

**Files:**
- Modify: `apps/api/app/processing/ingest_persistence.py`
- Test: `apps/api/tests/test_ingest_persistence.py`

- [ ] **Step 1: Write the failing contract tests for candidate and extracted payload shapes**

```python
def test_build_ingest_candidate_submission_serializes_discovery_fields(tmp_path):
    from app.processing.ingest_persistence import build_ingest_candidate_submission

    source_root = tmp_path / "library"
    source_root.mkdir()
    photo_path = source_root / "sample.jpg"
    photo_path.write_bytes(b"candidate-bytes")

    payload = build_ingest_candidate_submission(
        photo_path,
        scan_root=source_root,
        canonical_path="/library/sample.jpg",
        storage_source_id="source-1",
        watched_folder_id="wf-1",
    )

    assert payload["payload_version"] == 1
    assert payload["storage_source_id"] == "source-1"
    assert payload["watched_folder_id"] == "wf-1"
    assert payload["canonical_path"] == "/library/sample.jpg"
    assert payload["runtime_path"] == str(photo_path.resolve())
    assert payload["relative_path"] == "sample.jpg"
    assert payload["idempotency_key"] == "wf-1:sample.jpg"
    assert "sha256" not in payload
    assert "faces" not in payload


def test_serialize_extracted_content_submission_includes_face_and_thumbnail_fields():
    from datetime import UTC, datetime

    from app.processing.ingest_persistence import PhotoRecord, serialize_extracted_content_submission

    record = PhotoRecord(
        photo_id="photo-1",
        path="/library/sample.jpg",
        sha256="abc123",
        filesize=123,
        ext="jpg",
        created_ts=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        modified_ts=datetime(2026, 4, 5, 12, 1, tzinfo=UTC),
        shot_ts=None,
        shot_ts_source=None,
        camera_make="Canon",
        camera_model="EOS",
        software=None,
        orientation="1",
        gps_latitude=None,
        gps_longitude=None,
        gps_altitude=None,
        thumbnail_jpeg=b"thumb",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        faces_count=1,
    )

    payload = serialize_extracted_content_submission(
        record=record,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="sample.jpg",
        detections=[
            {
                "face_id": "face-1",
                "bbox_x": 1,
                "bbox_y": 2,
                "bbox_w": 3,
                "bbox_h": 4,
                "bitmap": None,
                "embedding": None,
                "provenance": {"detector": "opencv"},
            }
        ],
        warnings=["face detection failed for sidecar"],
    )

    assert payload["payload_version"] == 1
    assert payload["sha256"] == "abc123"
    assert payload["faces_count"] == 1
    assert payload["detections"][0]["face_id"] == "face-1"
    assert payload["warnings"] == ["face detection failed for sidecar"]
```

- [ ] **Step 2: Run the payload contract tests to verify they fail**

Run: `uv run python -m pytest apps/api/tests/test_ingest_persistence.py -k "candidate_submission or extracted_content_submission" -q`

Expected: `FAIL` because `build_ingest_candidate_submission` and `serialize_extracted_content_submission` do not exist yet.

- [ ] **Step 3: Add minimal payload builders and serializers in `ingest_persistence.py`**

```python
def build_ingest_candidate_submission(
    path: Path,
    *,
    scan_root: Path,
    canonical_path: str,
    storage_source_id: str,
    watched_folder_id: str,
) -> dict:
    stat = path.stat()
    relative_path = relative_photo_path(scan_root, path)
    return {
        "payload_version": 1,
        "storage_source_id": storage_source_id,
        "watched_folder_id": watched_folder_id,
        "canonical_path": canonical_path,
        "runtime_path": str(path.resolve()),
        "relative_path": relative_path,
        "filesize": stat.st_size,
        "modified_ts": _normalize_timestamp(_parse_timestamp(stat_timestamp_to_iso(stat.st_mtime))).isoformat(),
        "idempotency_key": f"{watched_folder_id}:{relative_path}",
    }


def serialize_extracted_content_submission(
    *,
    record: PhotoRecord,
    storage_source_id: str,
    watched_folder_id: str,
    relative_path: str,
    detections: list[dict],
    warnings: list[str],
) -> dict:
    payload = _serialize_record(record)
    payload.update(
        {
            "payload_version": 1,
            "storage_source_id": storage_source_id,
            "watched_folder_id": watched_folder_id,
            "relative_path": relative_path,
            "detections": detections,
            "warnings": warnings,
        }
    )
    return payload


def serialize_reused_content_submission(
    *,
    record: PhotoRecord,
    candidate_payload: dict,
    warnings: list[str],
) -> dict:
    payload = _serialize_record(record)
    payload.update(
        {
            "payload_version": 1,
            "storage_source_id": candidate_payload["storage_source_id"],
            "watched_folder_id": candidate_payload["watched_folder_id"],
            "relative_path": candidate_payload["relative_path"],
            "detections": [],
            "warnings": warnings,
        }
    )
    return payload
```

- [ ] **Step 4: Run the payload contract tests to verify they pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest_persistence.py -k "candidate_submission or extracted_content_submission" -q`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/processing/ingest_persistence.py apps/api/tests/test_ingest_persistence.py
git commit -m "feat: define staged ingest payload contracts"
```

### Task 2: Add The Extraction Worker With SHA Short-Circuiting

**Files:**
- Create: `apps/api/app/services/ingest_extraction_worker.py`
- Modify: `apps/api/app/processing/ingest_persistence.py`
- Test: `apps/api/tests/test_ingest_extraction_worker.py`

- [ ] **Step 1: Write the failing extraction-worker tests for known and new content**

```python
def test_process_candidate_reuses_existing_sha_without_running_face_detection(tmp_path, monkeypatch):
    from app.services.ingest_extraction_worker import process_candidate_payload

    candidate = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/dup.jpg",
        "runtime_path": str((tmp_path / "dup.jpg").resolve()),
        "relative_path": "dup.jpg",
        "idempotency_key": "wf-1:dup.jpg",
    }

    calls = {"detect": 0}

    class Detector:
        def detect(self, path):
            calls["detect"] += 1
            return []

    monkeypatch.setattr(
        "app.services.ingest_extraction_worker.lookup_existing_artifacts_by_sha",
        lambda connection, sha256: {"metadata_complete": True, "thumbnail_complete": True, "faces_complete": True},
    )

    result = process_candidate_payload(
        database_url=f"sqlite:///{tmp_path / 'worker.db'}",
        payload=candidate,
        face_detector=Detector(),
    )

    assert result.reused_existing_artifacts is True
    assert result.analysis_performed is False
    assert calls["detect"] == 0


def test_process_candidate_runs_analysis_for_new_sha(tmp_path):
    from app.services.ingest_extraction_worker import process_candidate_payload

    photo_path = tmp_path / "new.jpg"
    photo_path.write_bytes(b"new-bytes")

    result = process_candidate_payload(
        database_url=f"sqlite:///{tmp_path / 'worker-new.db'}",
        payload={
            "payload_version": 1,
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/new.jpg",
            "runtime_path": str(photo_path.resolve()),
            "relative_path": "new.jpg",
            "idempotency_key": "wf-1:new.jpg",
        },
    )

    assert result.reused_existing_artifacts is False
    assert result.analysis_performed is True
    assert result.extracted_payload["sha256"]
    assert "detections" in result.extracted_payload
```

- [ ] **Step 2: Run the extraction-worker tests to verify they fail**

Run: `uv run python -m pytest apps/api/tests/test_ingest_extraction_worker.py -q`

Expected: `FAIL` because the worker module and SHA reuse helpers do not exist yet.

- [ ] **Step 3: Add a focused extraction worker module and artifact lookup helper**

```python
@dataclass(frozen=True)
class ExtractionResult:
    extracted_payload: dict
    reused_existing_artifacts: bool
    analysis_performed: bool


def process_candidate_payload(
    database_url: str | Path | None,
    *,
    payload: dict,
    face_detector=None,
) -> ExtractionResult:
    runtime_path = Path(payload["runtime_path"])
    record = build_photo_record(runtime_path, canonical_path=payload["canonical_path"])
    engine = create_db_engine(database_url)

    with engine.begin() as connection:
        existing = lookup_existing_artifacts_by_sha(connection, record.sha256)
        if existing is not None and all(existing.values()):
            extracted_payload = serialize_reused_content_submission(
                record=record,
                candidate_payload=payload,
                warnings=[],
            )
            return ExtractionResult(
                extracted_payload=extracted_payload,
                reused_existing_artifacts=True,
                analysis_performed=False,
            )

    thumbnail = generate_thumbnail(runtime_path)
    detections = _detect_faces(runtime_path, detector=face_detector)
    enriched = PhotoRecord(
        **{
            **record.__dict__,
            "thumbnail_jpeg": thumbnail.jpeg_bytes,
            "thumbnail_mime_type": thumbnail.mime_type,
            "thumbnail_width": thumbnail.width,
            "thumbnail_height": thumbnail.height,
            "faces_count": len(detections),
        }
    )
    return ExtractionResult(
        extracted_payload=serialize_extracted_content_submission(
            record=enriched,
            storage_source_id=payload["storage_source_id"],
            watched_folder_id=payload["watched_folder_id"],
            relative_path=payload["relative_path"],
            detections=detections,
            warnings=[],
        ),
        reused_existing_artifacts=False,
        analysis_performed=True,
    )
```

- [ ] **Step 4: Run the extraction-worker tests to verify they pass**

Run: `uv run python -m pytest apps/api/tests/test_ingest_extraction_worker.py -q`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ingest_extraction_worker.py apps/api/app/processing/ingest_persistence.py apps/api/tests/test_ingest_extraction_worker.py
git commit -m "feat: add staged extraction worker"
```

### Task 3: Refactor Polling Into Discovery And Candidate Enqueueing

**Files:**
- Modify: `apps/api/app/processing/ingest_polling.py`
- Modify: `apps/api/app/db/queue.py`
- Test: `apps/api/tests/test_ingest_polling.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing polling tests for candidate enqueueing**

```python
def test_poll_registered_storage_sources_enqueues_candidate_payloads_without_inline_thumbnail_work(
    tmp_path,
    monkeypatch,
):
    import app.processing.ingest_polling as ingest_polling
    from app.db.queue import IngestQueueStore

    database_url = f"sqlite:///{tmp_path / 'poll-discovery.db'}"
    enqueued_payloads = []

    def record_enqueue(self, *, payload_type, payload, idempotency_key):
        enqueued_payloads.append((payload_type, payload, idempotency_key))
        return "queue-1"

    monkeypatch.setattr(IngestQueueStore, "enqueue", record_enqueue)

    def fail_thumbnail(path):
        raise AssertionError("thumbnail generation should not run during polling")

    monkeypatch.setattr(ingest_polling, "generate_thumbnail", fail_thumbnail)

    result = ingest_polling.poll_registered_storage_sources(database_url=database_url)

    assert result.scanned == 1
    assert result.enqueued == 1
    assert enqueued_payloads[0][0] == "ingest_candidate"
    assert "runtime_path" in enqueued_payloads[0][1]
    assert "sha256" not in enqueued_payloads[0][1]
```

- [ ] **Step 2: Run the polling enqueue test to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -k "candidate_payloads_without_inline_thumbnail_work" -q`

Expected: `FAIL` because polling still builds records and thumbnails inline and does not enqueue candidate payloads.

- [ ] **Step 3: Change the polling chunk processor to enqueue candidate payloads and keep bookkeeping**

```python
queue_store = IngestQueueStore(database_url)


def _enqueue_watched_folder_candidate(
    *,
    queue_store: IngestQueueStore,
    photo_path: Path,
    source_root: Path,
    watched_folder_id: str,
    storage_source_id: str,
    canonical_path_for_relative_path: Callable[[str], str],
) -> tuple[str, str]:
    relative_path = relative_photo_path(source_root, photo_path)
    payload = build_ingest_candidate_submission(
        photo_path,
        scan_root=source_root,
        canonical_path=canonical_path_for_relative_path(relative_path),
        storage_source_id=storage_source_id,
        watched_folder_id=watched_folder_id,
    )
    queue_id = queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=payload,
        idempotency_key=payload["idempotency_key"],
    )
    return relative_path, queue_id
```

```python
for photo_path in photo_paths:
    scanned += 1
    relative_path, _queue_id = _enqueue_watched_folder_candidate(
        queue_store=queue_store,
        photo_path=photo_path,
        source_root=source_root,
        watched_folder_id=watched_folder_id,
        storage_source_id=storage_source_id,
        canonical_path_for_relative_path=canonical_path_for_relative_path,
    )
    observed_relative_paths.add(relative_path)
```

- [ ] **Step 4: Run the focused polling tests and the facade regression tests**

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -k "candidate_payloads_without_inline_thumbnail_work or completed_run_per_chunk" -q`

Expected: `PASS`

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources" -q`

Expected: `PASS`, with assertions updated for enqueue-oriented poll behavior where needed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/processing/ingest_polling.py apps/api/app/db/queue.py apps/api/tests/test_ingest_polling.py apps/api/tests/test_ingest.py
git commit -m "refactor: make polling discovery-only"
```

### Task 4: Make Queue Processing Persist Extracted Payloads Instead Of Running Face Detection

**Files:**
- Modify: `apps/api/app/services/ingest_queue_processor.py`
- Modify: `apps/api/app/processing/ingest_persistence.py`
- Test: `apps/api/tests/test_ingest_queue_processor.py`

- [ ] **Step 1: Write the failing queue-processor tests for extracted payload persistence**

```python
def test_process_pending_ingest_queue_persists_face_detections_from_extracted_payload(tmp_path, monkeypatch):
    from app.db.queue import IngestQueueStore
    from app.services.ingest_queue_processor import process_pending_ingest_queue

    database_url = f"sqlite:///{tmp_path / 'queue-persist.db'}"
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="extracted_photo",
        payload={
            "payload_version": 1,
            "photo_id": "photo-1",
            "path": "/library/sample.jpg",
            "sha256": "abc123",
            "filesize": 123,
            "ext": "jpg",
            "created_ts": "2026-04-05T12:00:00+00:00",
            "modified_ts": "2026-04-05T12:00:00+00:00",
            "shot_ts": None,
            "shot_ts_source": None,
            "camera_make": None,
            "camera_model": None,
            "software": None,
            "orientation": None,
            "gps_latitude": None,
            "gps_longitude": None,
            "gps_altitude": None,
            "faces_count": 1,
            "detections": [
                {
                    "face_id": "face-1",
                    "bbox_x": 1,
                    "bbox_y": 2,
                    "bbox_w": 3,
                    "bbox_h": 4,
                    "bitmap": None,
                    "embedding": None,
                    "provenance": {"detector": "opencv"},
                }
            ],
            "warnings": [],
        },
        idempotency_key="photo-1",
    )

    def fail_detect(path):
        raise AssertionError("queue persistence should not run face detection")

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=type("Detector", (), {"detect": fail_detect})(),
    )

    assert result.processed == 1
```

- [ ] **Step 2: Run the extracted-payload queue test to verify it fails**

Run: `uv run python -m pytest apps/api/tests/test_ingest_queue_processor.py -k "persists_face_detections_from_extracted_payload" -q`

Expected: `FAIL` because the processor only accepts `photo_metadata` payloads and still calls `_apply_face_detection()`.

- [ ] **Step 3: Route payload types explicitly and keep persistence free of media analysis**

```python
if claimed_row.payload_type == "ingest_candidate":
    extraction_result = process_candidate_payload(
        database_url,
        payload=claimed_row.payload_json,
        face_detector=detector,
    )
    queue_store.mark_completed(
        claimed_row.ingest_queue_id,
        last_error=_warning_summary(extraction_result.extracted_payload.get("warnings", [])),
        connection=connection,
    )
    queue_store.enqueue(
        payload_type="extracted_photo",
        payload=extraction_result.extracted_payload,
        idempotency_key=extraction_result.extracted_payload["photo_id"],
    )
    continue

if claimed_row.payload_type == "extracted_photo":
    record = payload_to_photo_record(claimed_row.payload_json)
    created = upsert_photo(connection, record)
    store_face_detections(
        connection,
        record.photo_id,
        claimed_row.payload_json.get("detections", []),
    )
    queue_store.mark_completed(
        claimed_row.ingest_queue_id,
        last_error=_warning_summary(claimed_row.payload_json.get("warnings", [])),
        connection=connection,
    )
    continue
```

- [ ] **Step 4: Run the queue-processor suite to verify the new routing works**

Run: `uv run python -m pytest apps/api/tests/test_ingest_queue_processor.py -q`

Expected: `PASS`, with older tests updated to reflect `ingest_candidate` and `extracted_photo` routing.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ingest_queue_processor.py apps/api/app/processing/ingest_persistence.py apps/api/tests/test_ingest_queue_processor.py
git commit -m "refactor: persist extracted ingest payloads"
```

### Task 5: Reuse Artifacts By SHA Across Duplicate-Content Paths

**Files:**
- Modify: `apps/api/app/processing/ingest_persistence.py`
- Modify: `apps/api/app/services/ingest_extraction_worker.py`
- Test: `apps/api/tests/test_ingest_persistence.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing reuse tests for duplicate-content files**

```python
def test_lookup_existing_artifacts_by_sha_reports_complete_face_thumbnail_and_metadata_state(tmp_path):
    from app.processing.ingest_persistence import lookup_existing_artifacts_by_sha

    database_url = f"sqlite:///{tmp_path / 'reuse.db'}"
    state = lookup_existing_artifacts_by_sha(database_url, "known-sha")

    assert state == {
        "metadata_complete": True,
        "thumbnail_complete": True,
        "faces_complete": True,
    }


def test_poll_and_process_duplicate_content_reuses_existing_artifacts(tmp_path):
    from sqlalchemy import create_engine, select

    from app.processing.ingest import poll_registered_storage_sources
    from app.services.ingest_queue_processor import process_pending_ingest_queue
    from photoorg_db_schema import photos

    database_url = f"sqlite:///{tmp_path / 'duplicate.db'}"

    first_result = poll_registered_storage_sources(database_url=database_url)
    second_result = poll_registered_storage_sources(database_url=database_url)
    process_pending_ingest_queue(database_url, limit=20)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        row = connection.execute(
            select(photos.c.faces_count).where(photos.c.path == "/library/dup.jpg")
        ).mappings().one()

    assert first_result.scanned == 1
    assert second_result.scanned == 1
    assert row["faces_count"] == 1
```

- [ ] **Step 2: Run the duplicate-content reuse tests to verify they fail**

Run: `uv run python -m pytest apps/api/tests/test_ingest_persistence.py -k "lookup_existing_artifacts_by_sha" -q`

Expected: `FAIL` because the lookup helper is not implemented.

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "duplicate_content_reuses_existing_artifacts" -q`

Expected: `FAIL` because the end-to-end flow does not yet short-circuit analysis by SHA.

- [ ] **Step 3: Implement the SHA completeness lookup and reuse path**

```python
def lookup_existing_artifacts_by_sha(connection: Connection, sha256: str) -> dict[str, bool] | None:
    row = connection.execute(
        select(
            photos.c.photo_id,
            photos.c.camera_make,
            photos.c.thumbnail_jpeg,
            photos.c.faces_detected_ts,
            photos.c.faces_count,
        ).where(photos.c.sha256 == sha256)
    ).mappings().first()
    if row is None:
        return None
    return {
        "metadata_complete": row["camera_make"] is not None,
        "thumbnail_complete": row["thumbnail_jpeg"] is not None,
        "faces_complete": row["faces_detected_ts"] is not None or row["faces_count"] == 0,
    }
```

```python
if existing is not None and all(existing.values()):
    return ExtractionResult(
        extracted_payload=serialize_reused_content_submission(
            record=record,
            candidate_payload=payload,
            warnings=[],
        ),
        reused_existing_artifacts=True,
        analysis_performed=False,
    )
```

- [ ] **Step 4: Run the reuse tests and targeted end-to-end regressions**

Run: `uv run python -m pytest apps/api/tests/test_ingest_persistence.py -k "lookup_existing_artifacts_by_sha" -q`

Expected: `PASS`

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "same_hash or duplicate_content_reuses_existing_artifacts or preserves_existing_face_detection_timestamp" -q`

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/processing/ingest_persistence.py apps/api/app/services/ingest_extraction_worker.py apps/api/tests/test_ingest_persistence.py apps/api/tests/test_ingest.py
git commit -m "feat: reuse extracted artifacts by sha"
```

### Task 6: Final Verification And Docs Alignment

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Test: `apps/api/tests/test_ingest_polling.py`
- Test: `apps/api/tests/test_ingest_queue_processor.py`
- Test: `apps/api/tests/test_ingest_extraction_worker.py`
- Test: `apps/api/tests/test_ingest.py`

- [ ] **Step 1: Add or update docs for the staged ingest flow**

```markdown
`poll-storage-sources` now performs discovery and candidate scheduling only.
Queued workers perform content hashing and, when needed, metadata extraction,
thumbnail generation, and face detection before persistence.
Duplicate-content files reuse existing extracted artifacts by SHA.
```

- [ ] **Step 2: Run the focused ingest verification suite**

Run: `uv run python -m pytest apps/api/tests/test_ingest_persistence.py -q`
Expected: `PASS`

Run: `uv run python -m pytest apps/api/tests/test_ingest_extraction_worker.py -q`
Expected: `PASS`

Run: `uv run python -m pytest apps/api/tests/test_ingest_polling.py -q`
Expected: `PASS`

Run: `uv run python -m pytest apps/api/tests/test_ingest_queue_processor.py -q`
Expected: `PASS`

Run: `uv run python -m pytest apps/api/tests/test_ingest.py -k "poll_registered_storage_sources or same_hash or face_detection" -q`
Expected: `PASS`

- [ ] **Step 3: Run one representative end-to-end local workflow**

Run: `uv run python -m pytest apps/e2e/tests/test_seed_corpus_workflow.py -q`

Expected: `PASS`, demonstrating staged polling plus downstream processing still produces searchable photos with persisted face regions.

- [ ] **Step 4: Commit**

```bash
git add README.md CONTRIBUTING.md apps/api/app apps/api/tests
git commit -m "docs: describe staged ingest analysis pipeline"
```
