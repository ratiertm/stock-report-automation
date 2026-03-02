"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.stocks import router as stocks_router
from app.api.watchlist import router as watchlist_router
from app.api.content import router as content_router
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Stock Report Hub",
    description="Stock research report parsing, storage, and comparison API",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(stocks_router)
app.include_router(watchlist_router)
app.include_router(content_router)


@app.get("/health")
def health():
    return {"status": "ok"}
