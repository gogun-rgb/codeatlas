from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

LOCAL_DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def allowed_origins() -> list[str]:
    origins = [*LOCAL_DEV_ORIGINS]
    configured = os.getenv("CODEATLAS_ALLOWED_ORIGINS", "")
    origins.extend(origin.strip() for origin in configured.split(","))
    return sorted({origin for origin in origins if origin and origin != "*"})


def create_app() -> FastAPI:
    app = FastAPI(title="CodeAtlas API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
