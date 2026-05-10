from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from config import get_settings, is_internal_shared_secret_configured
from database import check_database_ready, create_tables
from routers import (
    coupons,
    identity_mappings,
    points,
    referrals,
    streamers,
    tachigo,
    webhooks,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Tachiya API", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(coupons.router)
app.include_router(identity_mappings.router)
app.include_router(points.router)
app.include_router(referrals.router)
app.include_router(streamers.router)
app.include_router(tachigo.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    checks = {}
    try:
        check_database_ready()
    except SQLAlchemyError:
        checks["database"] = "error"
    else:
        checks["database"] = "ok"

    checks["internal_secret"] = (
        "ok" if is_internal_shared_secret_configured() else "error"
    )

    if "error" in checks.values():
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": checks},
        )

    return {"status": "ok", "checks": checks}
