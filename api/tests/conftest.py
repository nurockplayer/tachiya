import sys
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base


def build_sqlite_session(*, static_pool: bool = False) -> Session:
    engine_kwargs: dict[str, Any] = {}
    if static_pool:
        engine_kwargs = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }

    engine = create_engine("sqlite:///:memory:", **engine_kwargs)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def build_router_client(
    router: APIRouter,
    db_dependency: Callable[[], Any],
    session: Session,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[db_dependency] = override_db
    return TestClient(app)


@pytest.fixture
def sqlite_session() -> Generator[Session, None, None]:
    session = build_sqlite_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def static_sqlite_session() -> Generator[Session, None, None]:
    session = build_sqlite_session(static_pool=True)
    try:
        yield session
    finally:
        session.close()
