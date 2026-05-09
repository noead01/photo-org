from __future__ import annotations

import base64
import math
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import and_, func, insert, select, update, delete
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.repositories.photos_repo import PhotosRepository
from app.schemas.search_response import ThumbnailHit
from app.schemas.search_request import SearchFilters, SortSpec, PageSpec
from app.storage import albums, editable_album_items, photos, saved_filter_album_rules


router = APIRouter(prefix="/albums", tags=["albums"])

AlbumKind = Literal["editable", "saved_filter"]
AlbumName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CreateAlbumRequest(BaseModel):
    name: AlbumName
    kind: AlbumKind = "editable"
    filter_json: dict[str, Any] | None = None


class UpdateAlbumRequest(BaseModel):
    name: AlbumName | None = None
    filter_json: dict[str, Any] | None = None


class AlbumResponse(BaseModel):
    album_id: str
    name: str
    owner_user_id: str
    kind: AlbumKind
    created_ts: datetime
    updated_ts: datetime
    item_count: int = Field(ge=0)
    saved_filter: dict[str, Any] | None = None


class AlbumItemResponse(BaseModel):
    photo_id: str
    path: str
    ext: str
    shot_ts: datetime | None
    filesize: int
    thumbnail: ThumbnailHit | None = None


class AlbumDetailResponse(AlbumResponse):
    items_total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
    items: list[AlbumItemResponse]


class AddAlbumItemsRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1)


class AddAlbumItemsResponse(BaseModel):
    album_id: str
    added_photo_ids: list[str]
    duplicate_photo_ids: list[str]
    missing_photo_ids: list[str]


def _resolve_user_id(header_value: str | None) -> str:
    candidate = (header_value or "").strip()
    return candidate if candidate else "demo-user"


def _normalize_photo_ids(photo_ids: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in photo_ids:
        normalized = raw.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _album_name_exists(db: Session, *, owner_user_id: str, name: str, exclude_album_id: str | None = None) -> bool:
    stmt = select(albums.c.album_id).where(
        and_(
            albums.c.owner_user_id == owner_user_id,
            func.lower(albums.c.name) == name.lower(),
        )
    )
    if exclude_album_id is not None:
        stmt = stmt.where(albums.c.album_id != exclude_album_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def _get_album_row(db: Session, *, album_id: str) -> dict[str, Any]:
    row = db.execute(
        select(albums).where(albums.c.album_id == album_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    return dict(row)


def _get_saved_filter(db: Session, *, album_id: str) -> dict[str, Any] | None:
    row = db.execute(
        select(saved_filter_album_rules.c.filter_json).where(saved_filter_album_rules.c.album_id == album_id)
    ).mappings().one_or_none()
    return None if row is None else row["filter_json"]


def _ensure_saved_filter_valid(filter_json: dict[str, Any] | None) -> dict[str, Any]:
    if filter_json is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Saved-filter albums require filter_json.",
        )
    validated = SearchFilters.model_validate(filter_json)
    return validated.model_dump(exclude_none=True)


def _raise_saved_filter_membership_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Saved-filter albums cannot be modified directly.",
    )


def _build_album_response(db: Session, album_row: dict[str, Any]) -> AlbumResponse:
    album_id = str(album_row["album_id"])
    kind = str(album_row["kind"])
    if kind == "editable":
        item_count = db.execute(
            select(func.count()).select_from(editable_album_items).where(editable_album_items.c.album_id == album_id)
        ).scalar_one()
        saved_filter = None
    else:
        item_count = 0
        saved_filter = _get_saved_filter(db, album_id=album_id)

    return AlbumResponse.model_validate(
        {
            "album_id": album_id,
            "name": album_row["name"],
            "owner_user_id": album_row["owner_user_id"],
            "kind": kind,
            "created_ts": album_row["created_ts"],
            "updated_ts": album_row["updated_ts"],
            "item_count": int(item_count),
            "saved_filter": saved_filter,
        }
    )


@router.post(
    "",
    summary="Create album",
    description="Create an in-app album container for photo references.",
    response_model=AlbumResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_album_endpoint(
    body: CreateAlbumRequest,
    db: Session = Depends(get_db),
    user_id_header: str | None = Header(default=None, alias="X-Photo-Org-User-Id"),
) -> AlbumResponse:
    user_id = _resolve_user_id(user_id_header)
    if _album_name_exists(db, owner_user_id=user_id, name=body.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Album name already exists. Choose a different name.",
        )

    now = datetime.now(tz=UTC)
    album_id = str(uuid4())
    db.execute(
        insert(albums).values(
            album_id=album_id,
            name=body.name,
            owner_user_id=user_id,
            kind=body.kind,
            created_ts=now,
            updated_ts=now,
        )
    )

    if body.kind == "saved_filter":
        validated_filter = _ensure_saved_filter_valid(body.filter_json)
        db.execute(
            insert(saved_filter_album_rules).values(
                album_id=album_id,
                filter_json=validated_filter,
                updated_ts=now,
            )
        )

    db.commit()
    created = _get_album_row(db, album_id=album_id)
    return _build_album_response(db, created)


@router.get(
    "",
    summary="List albums",
    description="Return albums ordered by last update timestamp.",
    response_model=list[AlbumResponse],
)
def list_albums_endpoint(db: Session = Depends(get_db)) -> list[AlbumResponse]:
    rows = (
        db.execute(
            select(albums)
            .order_by(albums.c.updated_ts.desc(), albums.c.album_id.asc())
        )
        .mappings()
        .all()
    )
    return [_build_album_response(db, dict(row)) for row in rows]


@router.get(
    "/{album_id}",
    summary="Get album detail",
    description="Return album metadata and current album members.",
    response_model=AlbumDetailResponse,
)
def get_album_detail_endpoint(
    album_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=120),
    db: Session = Depends(get_db),
) -> AlbumDetailResponse:
    album_row = _get_album_row(db, album_id=album_id)
    album_payload = _build_album_response(db, album_row)
    offset = (page - 1) * page_size

    if album_payload.kind == "editable":
        items_total = int(
            db.execute(
                select(func.count())
                .select_from(
                    editable_album_items.join(
                        photos,
                        editable_album_items.c.photo_id == photos.c.photo_id,
                    )
                )
                .where(editable_album_items.c.album_id == album_id)
                .where(photos.c.deleted_ts.is_(None))
            ).scalar_one()
        )
        item_rows = (
            db.execute(
                select(
                    photos.c.photo_id,
                    photos.c.path,
                    photos.c.ext,
                    photos.c.shot_ts,
                    photos.c.filesize,
                    photos.c.thumbnail_jpeg,
                    photos.c.thumbnail_mime_type,
                    photos.c.thumbnail_width,
                    photos.c.thumbnail_height,
                )
                .select_from(
                    editable_album_items.join(
                        photos,
                        editable_album_items.c.photo_id == photos.c.photo_id,
                    )
                )
                .where(editable_album_items.c.album_id == album_id)
                .where(photos.c.deleted_ts.is_(None))
                .order_by(editable_album_items.c.added_ts.desc(), photos.c.photo_id.asc())
                .offset(offset)
                .limit(page_size)
            )
            .mappings()
            .all()
        )
        items = [
            AlbumItemResponse.model_validate(
                {
                    "photo_id": row["photo_id"],
                    "path": row["path"],
                    "ext": row["ext"],
                    "shot_ts": row["shot_ts"],
                    "filesize": row["filesize"],
                    "thumbnail": (
                        {
                            "mime_type": row["thumbnail_mime_type"],
                            "width": int(row["thumbnail_width"]),
                            "height": int(row["thumbnail_height"]),
                            "data_base64": base64.b64encode(row["thumbnail_jpeg"]).decode("ascii"),
                        }
                        if row["thumbnail_jpeg"]
                        and row["thumbnail_mime_type"]
                        and row["thumbnail_width"]
                        and row["thumbnail_height"]
                        else None
                    ),
                }
            )
            for row in item_rows
        ]
    else:
        saved_filter = album_payload.saved_filter or {}
        filters = SearchFilters.model_validate(saved_filter)
        repo = PhotosRepository(db)
        results, total, _ = repo.search_photos(
            filters=filters,
            sort=SortSpec(),
            page=PageSpec(limit=page_size, offset=offset),
            text_query=None,
        )
        items = [
            AlbumItemResponse.model_validate(
                {
                    "photo_id": row["photo_id"],
                    "path": row["path"],
                    "ext": row["ext"],
                    "shot_ts": row["shot_ts"],
                    "filesize": row["filesize"],
                    "thumbnail": row.get("thumbnail"),
                }
            )
            for row in results
        ]
        items_total = total

    total_pages = math.ceil(items_total / page_size) if items_total > 0 else 0

    return AlbumDetailResponse(
        **album_payload.model_dump(),
        items_total=items_total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.patch(
    "/{album_id}",
    summary="Update album",
    description="Rename album and optionally update saved-filter rules.",
    response_model=AlbumResponse,
)
def update_album_endpoint(
    album_id: str,
    body: UpdateAlbumRequest,
    db: Session = Depends(get_db),
    user_id_header: str | None = Header(default=None, alias="X-Photo-Org-User-Id"),
) -> AlbumResponse:
    album_row = _get_album_row(db, album_id=album_id)
    now = datetime.now(tz=UTC)
    next_name = body.name if body.name is not None else album_row["name"]
    owner_user_id = _resolve_user_id(user_id_header)

    if _album_name_exists(
        db,
        owner_user_id=owner_user_id,
        name=next_name,
        exclude_album_id=album_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Album name already exists. Choose a different name.",
        )

    db.execute(
        update(albums)
        .where(albums.c.album_id == album_id)
        .values(name=next_name, updated_ts=now)
    )

    if album_row["kind"] == "saved_filter" and body.filter_json is not None:
        validated_filter = _ensure_saved_filter_valid(body.filter_json)
        db.execute(
            update(saved_filter_album_rules)
            .where(saved_filter_album_rules.c.album_id == album_id)
            .values(filter_json=validated_filter, updated_ts=now)
        )

    db.commit()
    updated = _get_album_row(db, album_id=album_id)
    return _build_album_response(db, updated)


@router.delete(
    "/{album_id}",
    summary="Delete album",
    description="Delete an album and all subtype records.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_album_endpoint(album_id: str, db: Session = Depends(get_db)) -> Response:
    album_exists = db.execute(
        select(albums.c.album_id).where(albums.c.album_id == album_id)
    ).scalar_one_or_none()
    if album_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    db.execute(delete(albums).where(albums.c.album_id == album_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{album_id}/items",
    summary="Add album items",
    description="Add photo references to an album and report duplicates/missing IDs.",
    response_model=AddAlbumItemsResponse,
)
def add_album_items_endpoint(
    album_id: str,
    body: AddAlbumItemsRequest,
    db: Session = Depends(get_db),
    user_id_header: str | None = Header(default=None, alias="X-Photo-Org-User-Id"),
) -> AddAlbumItemsResponse:
    user_id = _resolve_user_id(user_id_header)
    normalized_photo_ids = _normalize_photo_ids(body.photo_ids)
    if not normalized_photo_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No valid photo IDs.")

    album_row = _get_album_row(db, album_id=album_id)
    if album_row["kind"] != "editable":
        _raise_saved_filter_membership_error()

    existing_photo_ids = set(
        db.execute(
            select(photos.c.photo_id)
            .where(photos.c.photo_id.in_(normalized_photo_ids))
            .where(photos.c.deleted_ts.is_(None))
        )
        .scalars()
        .all()
    )

    existing_album_items = set(
        db.execute(
            select(editable_album_items.c.photo_id)
            .where(editable_album_items.c.album_id == album_id)
            .where(editable_album_items.c.photo_id.in_(normalized_photo_ids))
        )
        .scalars()
        .all()
    )

    added_photo_ids: list[str] = []
    duplicate_photo_ids: list[str] = []
    missing_photo_ids: list[str] = []

    now = datetime.now(tz=UTC)
    for photo_id in normalized_photo_ids:
        if photo_id not in existing_photo_ids:
            missing_photo_ids.append(photo_id)
            continue
        if photo_id in existing_album_items:
            duplicate_photo_ids.append(photo_id)
            continue

        db.execute(
            insert(editable_album_items).values(
                album_id=album_id,
                photo_id=photo_id,
                added_by_user_id=user_id,
                added_ts=now,
            )
        )
        added_photo_ids.append(photo_id)

    db.execute(
        update(albums)
        .where(albums.c.album_id == album_id)
        .values(updated_ts=now)
    )
    db.commit()

    return AddAlbumItemsResponse(
        album_id=album_id,
        added_photo_ids=added_photo_ids,
        duplicate_photo_ids=duplicate_photo_ids,
        missing_photo_ids=missing_photo_ids,
    )


@router.delete(
    "/{album_id}/items/{photo_id}",
    summary="Remove album item",
    description="Remove a single photo reference from an editable album.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_album_item_endpoint(album_id: str, photo_id: str, db: Session = Depends(get_db)) -> Response:
    album_row = _get_album_row(db, album_id=album_id)
    if album_row["kind"] != "editable":
        _raise_saved_filter_membership_error()

    db.execute(
        delete(editable_album_items)
        .where(editable_album_items.c.album_id == album_id)
        .where(editable_album_items.c.photo_id == photo_id)
    )
    db.execute(
        update(albums)
        .where(albums.c.album_id == album_id)
        .values(updated_ts=datetime.now(tz=UTC))
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
