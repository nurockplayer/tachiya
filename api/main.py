from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from config import get_settings
from database import check_database_ready, create_tables
from routers import coupons, identity_mappings, points, referrals, streamers, tachigo


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        check_database_ready()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": {"database": "error"}},
        )

    return {"status": "ok", "checks": {"database": "ok"}}
