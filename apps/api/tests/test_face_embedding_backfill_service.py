from __future__ import annotations

import io
from datetime import UTC, datetime

from PIL import Image
from sqlalchemy import create_engine, insert, select

from app.migrations import upgrade_database
from app.services.face_embedding_backfill import (
    FaceEmbeddingModelUnavailableError,
    reembed_missing_face_embeddings,
)
from app.storage import faces, people, photos


def _insert_photo(connection, *, photo_id: str) -> None:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(photos).values(
            photo_id=photo_id,
            path=f"/library/{photo_id}.jpg",
            sha256=f"sha256-{photo_id}",
            created_ts=now,
            updated_ts=now,
            modified_ts=now,
            ext="jpg",
            filesize=123,
        )
    )


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 90, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_reembed_missing_face_embeddings_updates_rows_and_counts(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'face-embedding-backfill.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    class _FakeExtractor:
        def __init__(self, _model_path: str):
            pass

        def extract(self, _image):  # noqa: ANN001
            return [0.6, 0.8] + ([0.0] * 126)

    monkeypatch.setenv(
        "FACE_RECOGNITION_SFACE_MODEL_FILE",
        "/models/opencv/face_recognition_sface_2021dec.onnx",
    )
    monkeypatch.setattr(
        "app.services.face_embedding_backfill.OpenCvSFaceEmbeddingExtractor",
        _FakeExtractor,
    )

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_photo(connection, photo_id="photo-2")
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "face-with-bitmap",
                    "photo_id": "photo-1",
                    "person_id": None,
                    "bitmap": _jpeg_bytes(),
                    "embedding": None,
                },
                {
                    "face_id": "face-no-bitmap",
                    "photo_id": "photo-2",
                    "person_id": None,
                    "bitmap": None,
                    "embedding": None,
                },
            ],
        )

        result = reembed_missing_face_embeddings(
            connection,
            limit=10,
            refresh_related=False,
            suggestion_limit=5,
        )
        embedding_row = connection.execute(
            select(faces.c.embedding).where(faces.c.face_id == "face-with-bitmap")
        ).scalar_one()

    assert result == {
        "scanned": 2,
        "updated": 1,
        "skipped_missing_bitmap": 1,
        "skipped_extraction_failed": 0,
        "refreshed_people": 0,
        "refreshed_suggestion_scopes": 0,
    }
    assert embedding_row is not None
    assert embedding_row[:2] == [0.6, 0.8]


def test_reembed_missing_face_embeddings_refreshes_impacted_people(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'face-embedding-backfill-refresh.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)

    class _FakeExtractor:
        def __init__(self, _model_path: str):
            pass

        def extract(self, _image):  # noqa: ANN001
            return [0.1] * 128

    refresh_people_calls: list[str] = []
    refresh_suggestion_calls: list[tuple[str, int]] = []

    monkeypatch.setenv(
        "FACE_RECOGNITION_SFACE_MODEL_FILE",
        "/models/opencv/face_recognition_sface_2021dec.onnx",
    )
    monkeypatch.setattr(
        "app.services.face_embedding_backfill.OpenCvSFaceEmbeddingExtractor",
        _FakeExtractor,
    )
    monkeypatch.setattr(
        "app.services.face_embedding_backfill.refresh_person_representation",
        lambda connection, *, person_id: refresh_people_calls.append(person_id),
    )
    monkeypatch.setattr(
        "app.services.face_embedding_backfill.refresh_face_suggestions_for_person_scope",
        lambda connection, *, person_id, limit: refresh_suggestion_calls.append((person_id, limit)),
    )

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(people).values(person_id="person-1", display_name="Olivier")
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-1",
                bitmap=_jpeg_bytes(),
                embedding=None,
            )
        )

        result = reembed_missing_face_embeddings(
            connection,
            limit=10,
            refresh_related=True,
            suggestion_limit=7,
        )

    assert result["updated"] == 1
    assert result["refreshed_people"] == 1
    assert result["refreshed_suggestion_scopes"] == 1
    assert refresh_people_calls == ["person-1"]
    assert refresh_suggestion_calls == [("person-1", 7)]


def test_reembed_missing_face_embeddings_raises_when_model_is_unset(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'face-embedding-backfill-config.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    monkeypatch.delenv("FACE_RECOGNITION_SFACE_MODEL_FILE", raising=False)

    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
                bitmap=_jpeg_bytes(),
                embedding=None,
            )
        )

        try:
            reembed_missing_face_embeddings(connection)
            raise AssertionError("expected FaceEmbeddingModelUnavailableError")
        except FaceEmbeddingModelUnavailableError as exc:
            assert "FACE_RECOGNITION_SFACE_MODEL_FILE" in str(exc)
