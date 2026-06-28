from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from datetime import date

class JobBase(BaseModel):
    id: UUID
    filename: str = Field(..., max_length=255)
    status: str = Field(..., max_length=50)
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class JobListItem(JobBase):
    pass

class JobUploadResponse(BaseModel):
    job_id: UUID
    status: str = Field(..., max_length=50)
    message: str = Field(..., max_length=255)

class SummaryStats(BaseModel):
    total_spend_inr: float
    total_spend_usd: float
    anomaly_count: int
    risk_level: str = Field(..., max_length=20)

    model_config = ConfigDict(from_attributes=True)

class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str = Field(..., max_length=50)
    filename: str = Field(..., max_length=255)
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = Field(None, max_length=2000)
    summary: Optional[SummaryStats] = None

    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    txn_id: str = Field(..., max_length=100)
    date: date
    merchant: str = Field(..., max_length=255)
    amount: float
    currency: str = Field(..., max_length=10)
    status: str = Field(..., max_length=50)
    category: str = Field(..., max_length=100)
    account_id: str = Field(..., max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)
    is_anomaly: bool
    anomaly_reason: Optional[str] = Field(None, max_length=1000)
    llm_category: Optional[str] = Field(None, max_length=100)
    llm_raw_response: Optional[str] = Field(None, max_length=4000)
    llm_failed: bool

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('date')
    def serialize_date(self, d: date, _info):
        return d.isoformat()

class FullSummaryResponse(BaseModel):
    total_spend_inr: float
    total_spend_usd: float
    top_merchants: List[str]
    anomaly_count: int
    narrative: str = Field(..., max_length=2000)
    risk_level: str = Field(..., max_length=20)

    model_config = ConfigDict(from_attributes=True)

class JobResultsResponse(BaseModel):
    job_id: UUID
    status: str = Field(..., max_length=50)
    summary: Optional[FullSummaryResponse] = None
    transactions: List[TransactionResponse] = []
    category_breakdown: Dict[str, Dict[str, float]] = {}

    model_config = ConfigDict(from_attributes=True)
