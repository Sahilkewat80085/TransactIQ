# ANTIGRAVITY AGENT PROMPT — Backend + DevOps Internship Assignment

---

## 🗂️ CONTEXT & YOUR WORKING DIRECTORY

You have been placed in a folder that contains exactly two files:

1. **`Backend_DevOps_Assignment.pdf`** — The official assignment specification document. **Read this first. Every decision you make must trace back to a requirement in this PDF.**
2. **`transactions.csv`** — The raw, intentionally dirty financial transactions dataset you will be processing. Approximately 90 rows, 9 columns.

---

## 🛑 MANDATORY FIRST STEP — READ THE PDF BEFORE TOUCHING ANYTHING ELSE

Before you write a single line of code, before you create any file, before you plan any folder structure — **open and read `Backend_DevOps_Assignment.pdf` in full.**

Extract and confirm you understand:
- All 4 API endpoints and their exact expected inputs/outputs
- The 5-step processing pipeline (cleaning → anomaly detection → LLM classification → LLM narrative → retry logic)
- The required tech stack (FastAPI or Django REST, PostgreSQL, Celery+Redis or RQ+Redis, Docker Compose)
- The suggested database schema (Job, Transaction, JobSummary tables)
- The submission requirements (public GitHub repo, README with curl examples, 3-min video, architecture diagram)

Also open `transactions.csv` and inspect:
- The column headers: `txn_id, date, merchant, amount, currency, status, category, account_id, notes`
- The exact data quality issues present: mixed date formats (`DD-MM-YYYY` and `YYYY/MM/DD`), dollar-sign prefixes on amounts, inconsistent currency casing (`inr` vs `INR`), inconsistent status casing (`success`, `failed`), blank `txn_id` fields, blank `category` fields, rows with `notes` saying `SUSPICIOUS` or `Duplicate?`

**Do not proceed past this reading phase until you have confirmed your understanding of both files.**

---

## ⏸️ CHECKPOINT #1 — STOP AND REPORT BEFORE ANY CODE IS WRITTEN

After reading both files, **stop completely** and present the user with the following structured report. Do not write any code yet. Do not create any folders yet. Do not scaffold anything yet.

Your report must include:

### 1. Assignment Summary (your own words)
A brief paragraph (3–5 sentences) summarising what this project is: what it does, who uses it, and what the end result looks like.

### 2. Chosen Tech Stack & Justification
State your choices for each of the following and briefly justify each:
- **API Framework**: FastAPI or Django REST Framework — and why
- **Job Queue**: Celery + Redis or RQ + Redis — and why
- **LLM Provider**: Which free-tier LLM you plan to use (Gemini 1.5 Flash, Ollama, etc.) and how you'll handle the API key via environment variable

### 3. Proposed Project Structure
Show the full directory tree you plan to create (before creating it). Example depth: top-level folders, key files like `docker-compose.yml`, `Dockerfile`, `main.py`/`app/`, worker file, models, routes, etc.

### 4. Database Schema Plan
Write out the three tables you plan to create with all column names and types:
- `Job`
- `Transaction`
- `JobSummary`

### 5. API Contract
For each of the 4 endpoints, state:
- Method + path
- What it accepts (request body / file / query params)
- What it returns (response shape in plain English or JSON example)

### 6. Pipeline Walkthrough
Step by step, describe exactly what happens inside the Celery/RQ worker when a job is picked up — from raw CSV ingestion to final `JobSummary` being saved.

### 7. LLM Batching Strategy
Explain how you will batch the LLM classification calls. How many rows per batch? What prompt will you send? What JSON structure do you expect back?

### 8. Anomaly Detection Logic
State the exact rules you will implement:
- Rule 1: `amount > 3x the median amount for that account_id` → flag as statistical outlier
- Rule 2: `currency == USD` AND `merchant` is a domestic-only brand (Swiggy, Ola, IRCTC, etc.) → flag as currency anomaly
List any edge cases you anticipate.

### 9. Docker Compose Plan
List each service you will define in `docker-compose.yml`:
- `api` (FastAPI/Django)
- `worker` (Celery/RQ)
- `redis`
- `postgres`
State which environment variables each service will need.

### 10. Known Risks / Assumptions
List any ambiguities, risks, or assumptions you're making that are NOT explicitly covered by the PDF.

---

## ⏸️ AWAIT USER APPROVAL BEFORE PROCEEDING

After presenting the above report, end your message with exactly this block:

```
---
✅ READY TO BUILD — AWAITING YOUR APPROVAL

Please review the plan above. Reply with one of:
  - "Approved — proceed" to begin implementation
  - Any corrections or changes you want made before I start
  
I will not write any code or create any files until you give the go-ahead.
---
```

**Do not continue. Wait.**

---

## 🔨 PHASE 2 — IMPLEMENTATION (Only after user approves)

Once the user approves (or approves with modifications), implement the project in the following strict order. Complete each phase fully before moving to the next. After each phase, briefly tell the user what was just built and what comes next.

### Phase 2A — Project Scaffold & Docker Setup
1. Create the full directory structure
2. Write `docker-compose.yml` with all 4 services (api, worker, redis, postgres)
3. Write `Dockerfile` for the API/worker image
4. Write `.env.example` with all required environment variables (LLM key, DB credentials, Redis URL)
5. Write `requirements.txt` with pinned versions
6. **Verify**: `docker compose config` passes without errors

### Phase 2B — Database Models & Migrations
1. Define SQLAlchemy (or Django) models for `Job`, `Transaction`, `JobSummary`
2. Set up Alembic migrations (or Django migrations)
3. **Verify**: migrations run cleanly inside the container

### Phase 2C — API Endpoints
Implement all 4 endpoints exactly as specified:
1. `POST /jobs/upload` — validate CSV, create Job(status=pending), enqueue task, return `job_id`
2. `GET /jobs/{job_id}/status` — return status + summary if completed
3. `GET /jobs/{job_id}/results` — return full structured output
4. `GET /jobs` — list all jobs, support `?status=` filter

For each endpoint, write the Pydantic response models (or Django serializers) first, then the route handler.

### Phase 2D — The Processing Worker
Implement the pipeline worker in this exact order:

**Step 1 — Data Cleaning**
- Parse both date formats (`DD-MM-YYYY` and `YYYY/MM/DD`) → ISO 8601 (`YYYY-MM-DD`)
- Strip `$` prefix from `amount` column → cast to `float`
- Uppercase `currency` and `status` fields
- Fill blank `category` with `'Uncategorised'`
- Generate a `txn_id` for rows where it is blank
- Drop exact duplicate rows (all columns identical)
- Write cleaned rows to `Transaction` table with `job_id` FK

**Step 2 — Anomaly Detection**
- For each `account_id`, compute the median `amount` across all its transactions
- Flag any transaction where `amount > 3 * median` → set `is_anomaly=True`, `anomaly_reason='Statistical outlier: amount exceeds 3x account median'`
- Flag any transaction where `currency='USD'` AND `merchant` is in the domestic-only list (`['Swiggy', 'Ola', 'IRCTC', 'Zomato', 'Jio Recharge', 'BigBasket', 'Blinkit', 'Nykaa', 'Meesho']`) → set `is_anomaly=True`, `anomaly_reason='Currency anomaly: USD used with domestic-only merchant'`

**Step 3 — LLM Batch Classification**
- Collect all transactions where `llm_category` is needed (blank category or `'Uncategorised'` after cleaning)
- Batch them in groups of up to 20 rows
- For each batch, send a single LLM call with a prompt that includes the transaction data as a JSON array and asks the model to return a JSON object mapping `txn_id → category`, where category must be one of: `Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other`
- Parse the response and update `llm_category` on each Transaction row
- Implement retry with exponential backoff (3 retries: 2s, 4s, 8s delays)
- If all retries fail for a batch, set `llm_failed=True` on those rows and continue

**Step 4 — LLM Narrative Summary**
- Make a single LLM call with a prompt that includes aggregate stats (total spend by currency, top merchants, anomaly count)
- Ask the model to return a JSON object with exactly these keys:
  ```json
  {
    "total_spend_inr": <float>,
    "total_spend_usd": <float>,
    "top_merchants": ["merchant1", "merchant2", "merchant3"],
    "anomaly_count": <int>,
    "narrative": "<2-3 sentences>",
    "risk_level": "low" | "medium" | "high"
  }
  ```
- Store this as a `JobSummary` row

**Step 5 — Finalise Job**
- Set `Job.status = 'completed'`
- Set `Job.completed_at = now()`
- If an unrecoverable error occurs at any step, set `Job.status = 'failed'` and write the error to `Job.error_message`

### Phase 2E — README
Write a `README.md` that includes:
1. **Prerequisites** (Docker, Docker Compose)
2. **Setup** (clone repo, copy `.env.example` to `.env`, fill in LLM key)
3. **Run** (`docker compose up --build`)
4. **Example curl requests** for all 4 endpoints, with real example responses
5. **Architecture overview** (text description — a diagram link can be added later)

---

## ✅ QUALITY RULES — ENFORCE THESE THROUGHOUT

- **The system must boot with a single `docker compose up` command.** No manual migrations, no manual Redis setup, no manual pip installs.
- **All environment-specific values** (DB password, LLM API key, Redis URL) must come from environment variables, never hardcoded.
- **LLM calls must be batched.** One call per row is a hard failure.
- **Retry logic must use exponential backoff**, not a fixed sleep.
- **The `POST /jobs/upload` endpoint must return immediately** with a `job_id` — it must not block waiting for processing to finish.
- **Data cleaning must be idempotent** — running it twice on the same input must produce the same output.
- **All API responses must be JSON.**
- **Error responses must include a human-readable `detail` field.**

---

## 📋 FINAL DELIVERY CHECKLIST

Before declaring the project complete, verify every item:

- [ ] `docker compose up --build` starts all services without errors
- [ ] `POST /jobs/upload` with `transactions.csv` returns a `job_id` in under 1 second
- [ ] `GET /jobs/{job_id}/status` returns `pending` → `processing` → `completed` as the job runs
- [ ] `GET /jobs/{job_id}/results` returns cleaned transactions, anomalies, category breakdown, and LLM narrative
- [ ] `GET /jobs` returns all jobs; `GET /jobs?status=completed` filters correctly
- [ ] At least 2 transactions are flagged as anomalies (statistical outlier or currency mismatch)
- [ ] Transactions with blank categories have an `llm_category` populated
- [ ] `JobSummary` contains `risk_level`, `narrative`, `top_merchants`, `total_spend_inr`, `total_spend_usd`
- [ ] `.env.example` exists and documents every variable
- [ ] `README.md` has working curl commands
- [ ] No API keys or secrets are committed to the repo

---

*This prompt was generated by Claude (Anthropic) based on the contents of `Backend_DevOps_Assignment.pdf` and `transactions.csv`. The agent should treat the PDF as the authoritative specification and this prompt as the execution framework.*
