import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.database import engine
from app.routes.jobs import router as jobs_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connectivity on startup
    retries = 5
    connected = False
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Successfully connected to the database.")
            connected = True
            break
        except (OperationalError, Exception) as e:
            logger.warning(
                f"Database connection attempt {attempt + 1}/{retries} failed. "
                f"Retrying in 2 seconds... Error: {e}"
            )
            time.sleep(2)
            
    if not connected:
        logger.error("Could not connect to the database on startup after retries.")
        raise RuntimeError("Database connection failure.")
        
    yield

app = FastAPI(
    title="TransactIQ API",
    description="AI-Powered Financial Transaction Processing Pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - restricted to specific origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-KEY"],
)

# Custom middleware to inject secure HTTP headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Include routers
app.include_router(jobs_router)

@app.get("/")
def read_root():
    return {
        "app": "TransactIQ API",
        "status": "running",
        "documentation": "/docs"
    }
