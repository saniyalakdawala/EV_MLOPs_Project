"""
FastAPI Main Application Entry Point
Smart EV Charging Infrastructure Database Backend
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db_pool, close_db_pool
from app.routers import stations, sessions, dba, geocoding

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database Connection Pool
    print("[SERVER STARTUP] Initializing database pool...")
    init_db_pool()
    yield
    # Shutdown: Close Database Connection Pool
    print("[SERVER SHUTDOWN] Closing database pool...")
    close_db_pool()

app = FastAPI(
    title="Smart EV Charging Infrastructure Database API",
    description="Advanced Database Management Systems (ADBMS) Project Backend. "
                "Provides GIS spatial searches, transactional port booking with row locks, "
                "session lifecycle management, and live DBA health diagnostics.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure Cross-Origin Resource Sharing (CORS) for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow local React Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(stations.router)
app.include_router(sessions.router)
app.include_router(dba.router)
app.include_router(geocoding.router)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
