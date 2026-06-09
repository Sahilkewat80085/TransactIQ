# TransactIQ: AI-Powered Transaction Processing Pipeline

TransactIQ is an asynchronous backend system that processes dirty financial transaction datasets, normalizes and cleans the data, flags statistical and currency anomalies, leverages Google Gemini 1.5 Flash (via batch processing) to classify missing spend categories, and produces an executive narrative summary with a risk assessment level.

---

## 🏗️ Architecture & Request Lifecycle

```
[Client] ---> POST /jobs/upload ---> [FastAPI App] ---> Enqueue Celery Task
                                          |
                                          v
                                    [Save CSV file]
                                          |
                                          v
                                   [Celery Worker]
                                          |
                        +-----------------+-----------------+
                        |                 |                 |
                        v                 v                 v
                [Data Cleaning]   [Anomaly Detection]  [LLM Batching]
                        |                 |                 |
                        +-----------------+-----------------+
                                          |
                                          v
                               [Save to PostgreSQL]
                                          |
                                          v
                              [Generate LLM Summary]
```

1. **Request Reception**: The client uploads a CSV file containing transactions. The API generates a unique `job_id`, saves the CSV to a shared storage directory, and enqueues a background task via Celery.
2. **Immediate Response**: The API returns the `job_id` and status `pending` immediately (<1s) without blocking.
3. **Task Dequeuing**: A Celery worker picks up the job and transitions its status to `processing`.
4. **Data Normalization**: Mixed date formats are normalized to ISO 8601 (`YYYY-MM-DD`), dollar signs are stripped, status/currency casing are normalized, and missing `txn_id`s are filled using idempotent stable hashes.
5. **Anomaly Detection**:
   - **Rule 1**: Outlier flagged if transaction `amount > 3x account median` spend.
   - **Rule 2**: Currency mismatch flagged if transaction currency is `USD` for domestic Indian brands.
6. **LLM Classification**: Transactions with missing/blank categories are batched (up to 20 per call) and classified using Google Gemini 1.5 Flash.
7. **Executive Summary**: Aggregated spending indicators are sent to Gemini to generate a narrative spending summary and overall risk level assessment (`low`, `medium`, `high`).
8. **Completion**: The worker updates the job status to `completed` (or `failed` with error traceback details).

---

## 🛠️ Tech Stack
- **API**: FastAPI, Uvicorn
- **Task Queue & Broker**: Celery, Redis
- **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic (migrations)
- **Data Wrangling**: Pandas, Python-dateutil
- **AI Integration**: Google Generative AI SDK (Gemini 1.5 Flash)

---

## 🚀 Getting Started

### 1. Prerequisites
- Docker & Docker Compose
- Google Gemini API Key (get a free one from [Google AI Studio](https://aistudio.google.com/))

### 2. Configuration Setup
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your Gemini API key:
```env
GEMINI_API_KEY=AIzaSy...
```

### 3. Launching the Services
Boot the entire system (database, Redis, API server, and worker) with a single command:
```bash
docker compose up --build
```
The API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 📡 API Reference & CURL Examples

### 1. Upload a CSV File
Upload a CSV dataset of transactions to start processing.
```bash
curl -X POST -F "file=@transactions.csv" http://localhost:8000/jobs/upload
```
**Response**:
```json
{
  "job_id": "35f8e5f2-959c-4573-bf01-6b22c7cc1930",
  "status": "pending",
  "message": "CSV upload accepted. Job enqueued for processing."
}
```

### 2. Poll Job Status
Retrieve the current status of the background execution job.
```bash
curl http://localhost:8000/jobs/35f8e5f2-959c-4573-bf01-6b22c7cc1930/status
```
**Response (when completed)**:
```json
{
  "job_id": "35f8e5f2-959c-4573-bf01-6b22c7cc1930",
  "status": "completed",
  "filename": "transactions.csv",
  "row_count_raw": 96,
  "row_count_clean": 90,
  "created_at": "2026-06-09T17:30:00Z",
  "completed_at": "2026-06-09T17:31:05Z",
  "error_message": null,
  "summary": {
    "total_spend_inr": 845209.43,
    "total_spend_usd": 48215.12,
    "anomaly_count": 5,
    "risk_level": "medium"
  }
}
```

### 3. Retrieve Full Results
Retrieve the detailed structured output of the job, including normalized transactions, anomalies, per-category breakdown, and narrative.
```bash
curl http://localhost:8000/jobs/35f8e5f2-959c-4573-bf01-6b22c7cc1930/results
```
**Response**:
```json
{
  "job_id": "35f8e5f2-959c-4573-bf01-6b22c7cc1930",
  "status": "completed",
  "summary": {
    "total_spend_inr": 845209.43,
    "total_spend_usd": 48215.12,
    "top_merchants": ["IRCTC", "Flipkart", "Ola"],
    "anomaly_count": 5,
    "narrative": "Spending was concentrated on transport and travel, particularly with IRCTC and Ola. A total of 5 anomalies were flagged including several large dollar amounts.",
    "risk_level": "medium"
  },
  "transactions": [
    {
      "txn_id": "TXN1065",
      "date": "2024-09-04",
      "merchant": "Flipkart",
      "amount": 10882.55,
      "currency": "INR",
      "status": "SUCCESS",
      "category": "Shopping",
      "account_id": "ACC003",
      "notes": "Refund expected",
      "is_anomaly": false,
      "anomaly_reason": null,
      "llm_category": null,
      "llm_failed": false
    }
  ],
  "category_breakdown": {
    "Shopping": {
      "INR": 10882.55,
      "USD": 0.0
    }
  }
}
```

### 4. List All Jobs
List all processed uploads, optionally filtering by status.
```bash
curl http://localhost:8000/jobs?status=completed
```
**Response**:
```json
[
  {
    "id": "35f8e5f2-959c-4573-bf01-6b22c7cc1930",
    "filename": "transactions.csv",
    "status": "completed",
    "row_count_raw": 96,
    "row_count_clean": 90,
    "created_at": "2026-06-09T17:30:00Z"
  }
]
```
