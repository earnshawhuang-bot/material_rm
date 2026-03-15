"""FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv()

from .routers import auth, actions, dashboard, enums, inventory, mapping, upload, users
from .config import settings
from .database import Base, engine
from .services.bootstrap import initialize_sqlite_demo

STATIC_DIR = Path(__file__).resolve().parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(upload.router)
app.include_router(inventory.router)
app.include_router(actions.router)
app.include_router(enums.router)
app.include_router(mapping.router)
app.include_router(users.router)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    initialize_sqlite_demo()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health_check():
    return {"status": "ok"}
