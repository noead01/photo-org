from fastapi import FastAPI
from app.routers.search import router as search_router

app = FastAPI(title="Photo Organizer API")

# Mount routers
app.include_router(search_router, prefix="/api/v1")

# Simple health for E2E bring-up
@app.get("/healthz")
def healthz():
    return {"status": "ok"}
