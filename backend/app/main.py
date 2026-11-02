"""
FastAPI Main Application Entry Point
Smart EV Charging Infrastructure Database Backend
"""
from contextlib import asynccontextmanager
import logging
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from app.config import settings
from app.config import validate_settings
from app.database import init_db_pool, close_db_pool
from app.routers import stations, sessions, dba, geocoding, forecast
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS
logger = logging.getLogger("voltgrid")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    validate_settings()
    logger.info("Starting VoltGrid API; initializing database pool")
    try:
        init_db_pool()
    except Exception as exc:
        # Keep the app (and forecast API) available when the optional local DB is offline.
        # Database-backed routes will retry through their connection helper when called.
        logger.warning("Database pool unavailable at startup (%s); database routes may be unavailable", type(exc).__name__)
    yield
    # Shutdown: Close Database Connection Pool
    logger.info("Stopping VoltGrid API; closing database pool")
    close_db_pool()

app = FastAPI(
    title="Smart EV Charging Infrastructure Database API",
    description="Advanced Database Management Systems (ADBMS) Project Backend. "
                "Provides GIS spatial searches, transactional port booking with row locks, "
                "session lifecycle management, and live DBA health diagnostics.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure cross-origin access for local browser clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(stations.router)
app.include_router(sessions.router)
app.include_router(dba.router)
app.include_router(geocoding.router)
app.include_router(forecast.router)

@app.middleware("http")
async def record_http_metrics(request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, path, "500").inc()
        HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
        raise
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
    return response

@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "project": "Smart EV Charging Infrastructure Database",
        "track": "ADBMS Spatial & DBA",
        "documentation": "/docs",
        "database": settings.DB_NAME,
        "db_host": settings.DB_HOST
    }

@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "ev-charging-backend"}

@app.get("/health", tags=["Health"], include_in_schema=False)
def service_health():
    return {"status": "healthy", "service": "voltgrid-api"}

@app.get("/ready", tags=["Health"], include_in_schema=False)
def service_readiness():
    from app.routers.forecast import readiness as forecast_readiness
    return forecast_readiness()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
