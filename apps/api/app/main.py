from fastapi import FastAPI
from app.routers.ingest_queue import router as ingest_queue_router
from app.routers.storage_sources import router as storage_sources_router

app = FastAPI(title="Photo Organizer API")

app.include_router(ingest_queue_router, prefix="/api/v1")
app.include_router(storage_sources_router, prefix="/api/v1")

# Simple health for E2E bring-up
@app.get("/healthz")
def healthz():
    return {"status": "ok"}
