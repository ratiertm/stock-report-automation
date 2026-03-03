"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.stocks import router as stocks_router
from app.api.watchlist import router as watchlist_router
from app.api.content import router as content_router
from app.api.auth import router as auth_router
from app.api.deps import verify_api_key
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

app.include_router(stocks_router, dependencies=[Depends(verify_api_key)])
app.include_router(watchlist_router, dependencies=[Depends(verify_api_key)])
app.include_router(content_router, dependencies=[Depends(verify_api_key)])
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
