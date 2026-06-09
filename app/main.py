from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.jobs import router as jobs_router

app = FastAPI(
    title="TransactIQ API",
    description="AI-Powered Financial Transaction Processing Pipeline",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs_router)

@app.get("/")
def read_root():
    return {
        "app": "TransactIQ API",
        "status": "running",
        "documentation": "/docs"
    }
