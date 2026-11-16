import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (registers tables)
from .database import Base, engine
from .routes.api import router
from .routes.live import router as live_router
from .routes.map import router as map_router
from .routes.recent import router as recent_router

app = FastAPI(title="DriveAnalytics Crash Data API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","), allow_methods=["GET"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)
app.include_router(router)
app.include_router(map_router)
app.include_router(live_router)
app.include_router(recent_router)


@app.get("/health")
def health():
    return {"status": "ok"}
