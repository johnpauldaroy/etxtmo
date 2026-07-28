from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.services.scheduler import evaluate_rules_once

settings = get_settings()
logger = logging.getLogger("textblast")
logging.basicConfig(level=logging.INFO)

_scheduler_task: asyncio.Task | None = None


async def scheduler_loop() -> None:
    while True:
        await asyncio.sleep(60)
        db = SessionLocal()
        try:
            generated = evaluate_rules_once(db)
            db.commit()
            if generated:
                logger.info("Generated %s campaigns from schedule rules", generated)
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Scheduler loop failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _scheduler_task
    # Dev bootstrap; production should run Alembic migrations first.
    Base.metadata.create_all(bind=engine)
    if settings.scheduler_enabled:
        _scheduler_task = asyncio.create_task(scheduler_loop())
    try:
        yield
    finally:
        if _scheduler_task:
            _scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _scheduler_task


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
