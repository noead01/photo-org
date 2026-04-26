from fastapi import FastAPI

from app.routers.face_assignments import router as face_assignments_router
from app.routers.ingest_queue import router as ingest_queue_router
from app.routers.operations import router as operations_router
from app.routers.people import router as people_router
from app.routers.photos import router as photos_router
from app.routers.storage_sources import router as storage_sources_router
from app.openapi_docs import openapi_yaml_response

app = FastAPI(
    title="Photo Organizer API",
    version="0.1.0",
    summary="Photo search, browsing, and storage-source management API.",
    description=(
        "Photo Organizer's OpenAPI contract is authored in the FastAPI routes and Pydantic "
        "models in this repository and checked in as generated output."
    ),
    openapi_tags=[
        {
            "name": "photos",
            "description": "Browse and inspect photo records and metadata.",
        },
        {
            "name": "people",
            "description": "Create and manage people identities used by face-labeling workflows.",
        },
        {
            "name": "face-labeling",
            "description": "Assign and correct detected face-to-person associations.",
        },
        {
            "name": "search",
            "description": "Search photos using text, filters, and similarity signals.",
        },
        {
            "name": "storage-sources",
            "description": "Register storage roots and manage watched folders.",
        },
        {
            "name": "internal-ingest-queue",
            "description": "Worker-only queue processing endpoint.",
        },
        {
            "name": "operations",
            "description": "Read-only operational activity and troubleshooting signals.",
        },
    ],
    redoc_url=None,
)

app.include_router(ingest_queue_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(face_assignments_router, prefix="/api/v1")
app.include_router(people_router, prefix="/api/v1")
app.include_router(photos_router, prefix="/api/v1")
app.include_router(storage_sources_router, prefix="/api/v1")


@app.get("/openapi.yaml", include_in_schema=False)
def openapi_yaml():
    return openapi_yaml_response(app.openapi())


# Simple health for E2E bring-up
@app.get(
    "/healthz",
    summary="Health check",
    description="Return a minimal readiness response for the HTTP service.",
    response_description="A small health payload used by local startup checks.",
)
def healthz():
    return {"status": "ok"}
