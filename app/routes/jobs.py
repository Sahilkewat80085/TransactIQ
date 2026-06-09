import os
import shutil
import uuid
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Job, Transaction, JobSummary
from app.schemas import JobUploadResponse, JobStatusResponse, JobResultsResponse, JobListItem, SummaryStats, FullSummaryResponse, TransactionResponse
from app.tasks import process_csv_task

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=JobUploadResponse, status_code=202)
def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Basic validation
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    # Generate unique job ID
    job_id = uuid.uuid4()
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}.csv")
    
    # Save the file to shared volume
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
    
    # Create DB entry for Job
    job = Job(
        id=job_id,
        filename=file.filename,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Enqueue processing task in Celery
    process_csv_task.delay(str(job_id))
    
    return JobUploadResponse(
        job_id=job.id,
        status=job.status,
        message="CSV upload accepted. Job enqueued for processing."
    )

@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    summary_stats = None
    if job.status == "completed" and job.summary:
        summary_stats = SummaryStats(
            total_spend_inr=job.summary.total_spend_inr,
            total_spend_usd=job.summary.total_spend_usd,
            anomaly_count=job.summary.anomaly_count,
            risk_level=job.summary.risk_level
        )
        
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        filename=job.filename,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        summary=summary_stats
    )

@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is in state '{job.status}' and is not completed yet."
        )
    
    # Get summary
    full_summary = None
    if job.summary:
        full_summary = FullSummaryResponse(
            total_spend_inr=job.summary.total_spend_inr,
            total_spend_usd=job.summary.total_spend_usd,
            top_merchants=job.summary.top_merchants,
            anomaly_count=job.summary.anomaly_count,
            narrative=job.summary.narrative,
            risk_level=job.summary.risk_level
        )
    
    # Get transactions
    transactions = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    txn_responses = [TransactionResponse.model_validate(t) for t in transactions]
    
    # Calculate category breakdown
    category_breakdown = {}
    for txn in transactions:
        category = txn.llm_category if txn.llm_category else txn.category
        if not category:
            category = "Uncategorised"
            
        currency = txn.currency.upper()
        amount = txn.amount
        
        if category not in category_breakdown:
            category_breakdown[category] = {}
        if currency not in category_breakdown[category]:
            category_breakdown[category][currency] = 0.0
            
        category_breakdown[category][currency] += amount
        
    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        summary=full_summary,
        transactions=txn_responses,
        category_breakdown=category_breakdown
    )

@router.get("", response_model=List[JobListItem])
def list_jobs(
    status: Optional[str] = Query(None, description="Filter jobs by status"),
    db: Session = Depends(get_db)
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    return jobs
