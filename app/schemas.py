from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import date

class JobBase(BaseModel):
    id: UUID
    filename: str
    status: str
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class JobListItem(JobBase):
    pass

class JobUploadResponse(BaseModel):
    job_id: UUID
    status: str
    message: str

class SummaryStats(BaseModel):
    total_spend_inr: float
    total_spend_usd: float
    anomaly_count: int
    risk_level: str

    model_config = ConfigDict(from_attributes=True)

class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    filename: str
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    summary: Optional[SummaryStats] = None

    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    txn_id: str
    date: date
    merchant: str
    amount: float
    currency: str
    status: str
    category: str
    account_id: str
    notes: Optional[str] = None
    is_anomaly: bool
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    llm_raw_response: Optional[str] = None
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
    narrative: str
    risk_level: str

    model_config = ConfigDict(from_attributes=True)

class JobResultsResponse(BaseModel):
    job_id: UUID
    status: str
    summary: Optional[FullSummaryResponse] = None
    transactions: List[TransactionResponse] = []
    category_breakdown: Dict[str, Dict[str, float]] = {}

    model_config = ConfigDict(from_attributes=True)
