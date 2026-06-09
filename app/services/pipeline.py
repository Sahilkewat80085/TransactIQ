import os
import hashlib
import logging
from datetime import datetime, date
import pandas as pd
from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Job, Transaction, JobSummary
from app.services.llm import classify_categories_batch, generate_narrative_summary

logger = logging.getLogger(__name__)

def parse_date_robust(val) -> date:
    """Parses date string with support for DD-MM-YYYY, YYYY/MM/DD, YYYY-MM-DD."""
    if pd.isna(val) or not str(val).strip():
        return date.today()
    val_str = str(val).strip()
    
    # Try common formats explicitly
    for fmt in ("%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue
            
    # Fallback to dateutil parser
    try:
        return date_parser.parse(val_str).date()
    except Exception:
        logger.warning(f"Could not parse date: {val_str}. Using today's date.")
        return date.today()

def clean_amount(val) -> float:
    """Strips currency symbols and parses to float."""
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    if val_str.startswith('$'):
        val_str = val_str[1:]
    try:
        return float(val_str)
    except ValueError:
        logger.warning(f"Could not parse amount: {val_str}. Using 0.0.")
        return 0.0

def generate_stable_txn_id(row, idx) -> str:
    """Generates an idempotent stable transaction ID if blank."""
    raw_str = f"{idx}-{row.get('date')}-{row.get('merchant')}-{row.get('amount')}-{row.get('account_id')}"
    h = hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:8].upper()
    return f"TXN_GEN_{h}"

def run_pipeline(job_id_str: str):
    """Executes the 5-step processing pipeline."""
    db: Session = SessionLocal()
    
    try:
        logger.info(f"Starting processing pipeline for job {job_id_str}")
        job = db.query(Job).filter(Job.id == job_id_str).first()
        if not job:
            logger.error(f"Job {job_id_str} not found in database.")
            return

        # 1. Update Job status
        job.status = "processing"
        db.commit()

        file_path = os.path.join("uploads", f"{job_id_str}.csv")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Uploaded CSV file not found at {file_path}")

        # Load CSV using pandas
        df = pd.read_csv(file_path)
        job.row_count_raw = len(df)
        db.commit()

        # Normalize column headers
        df.columns = [c.strip().lower() for c in df.columns]

        # Drop exact duplicates
        df = df.drop_duplicates()
        job.row_count_clean = len(df)
        db.commit()

        # Pre-process lists to calculate medians
        # We need to parse amounts and account_ids before calculating medians
        df['cleaned_amount'] = df['amount'].apply(clean_amount)
        df['cleaned_account_id'] = df['account_id'].fillna('').astype(str).str.strip()
        
        # Calculate medians per account_id
        medians = df.groupby('cleaned_account_id')['cleaned_amount'].median().to_dict()

        domestic_brands = ['swiggy', 'ola', 'irctc', 'zomato', 'jio recharge', 'bigbasket', 'blinkit', 'nykaa', 'meesho']
        
        transactions_to_insert = []
        
        # 2. Iterate and apply cleaning + anomaly detection
        for idx, row in df.iterrows():
            # Clean fields
            raw_txn_id = str(row.get('txn_id', '')).strip()
            txn_id = raw_txn_id if raw_txn_id and raw_txn_id != 'nan' else generate_stable_txn_id(row, idx)
            
            txn_date = parse_date_robust(row.get('date'))
            merchant = str(row.get('merchant', '')).strip()
            amount = row['cleaned_amount']
            currency = str(row.get('currency', '')).strip().upper()
            status = str(row.get('status', '')).strip().upper()
            
            raw_cat = str(row.get('category', '')).strip()
            category = raw_cat if raw_cat and raw_cat != 'nan' else 'Uncategorised'
            
            account_id = row['cleaned_account_id']
            notes = str(row.get('notes', '')).strip() if not pd.isna(row.get('notes')) else None
            
            # Anomaly Detection
            is_anomaly = False
            anomaly_reasons = []
            
            # Rule 1: Statistical outlier
            median_val = medians.get(account_id, 0.0)
            if amount > 3 * median_val:
                is_anomaly = True
                anomaly_reasons.append("Statistical outlier: amount exceeds 3x account median")
                
            # Rule 2: Currency mismatch
            if currency == 'USD' and merchant.lower() in domestic_brands:
                is_anomaly = True
                anomaly_reasons.append("Currency anomaly: USD used with domestic-only merchant")
                
            anomaly_reason = "; ".join(anomaly_reasons) if is_anomaly else None
            
            # Create Transaction model
            txn = Transaction(
                job_id=job.id,
                txn_id=txn_id,
                date=txn_date,
                merchant=merchant,
                amount=amount,
                currency=currency,
                status=status,
                category=category,
                account_id=account_id,
                notes=notes,
                is_anomaly=is_anomaly,
                anomaly_reason=anomaly_reason
            )
            transactions_to_insert.append(txn)

        # Bulk save transactions
        db.add_all(transactions_to_insert)
        db.commit()

        # 3. LLM Category Classification for 'Uncategorised'
        uncategorized_txns = db.query(Transaction).filter(
            Transaction.job_id == job.id,
            Transaction.category == 'Uncategorised'
        ).all()

        if uncategorized_txns:
            logger.info(f"Found {len(uncategorized_txns)} uncategorized transactions to classify.")
            # Batch in chunks of 20
            batch_size = 20
            for i in range(0, len(uncategorized_txns), batch_size):
                batch = uncategorized_txns[i:i + batch_size]
                
                # Format payload
                payload = [
                    {
                        "txn_id": t.txn_id,
                        "merchant": t.merchant,
                        "amount": t.amount,
                        "notes": t.notes or ""
                    }
                    for t in batch
                ]
                
                try:
                    classification_map = classify_categories_batch(payload)
                    # Update DB for each transaction in the batch
                    for t in batch:
                        cat = classification_map.get(t.txn_id)
                        if cat:
                            t.llm_category = cat
                        else:
                            t.llm_failed = True
                except Exception as e:
                    logger.error(f"Failed to classify batch: {str(e)}")
                    # Mark all as failed in this batch
                    for t in batch:
                        t.llm_failed = True
            db.commit()

        # 4. LLM Narrative Summary
        # Compute aggregates
        all_txns = db.query(Transaction).filter(Transaction.job_id == job.id).all()
        total_inr = sum(t.amount for t in all_txns if t.currency == 'INR')
        total_usd = sum(t.amount for t in all_txns if t.currency == 'USD')
        anomaly_count = sum(1 for t in all_txns if t.is_anomaly)
        
        # Top merchants by transaction count
        merchant_counts = pd.Series([t.merchant for t in all_txns]).value_counts()
        top_merchants = merchant_counts.head(3).index.tolist()
        
        stats_payload = {
            "total_spend_inr": float(total_inr),
            "total_spend_usd": float(total_usd),
            "top_merchants": top_merchants,
            "anomaly_count": int(anomaly_count)
        }
        
        # Call LLM Narrative
        summary_data = generate_narrative_summary(stats_payload)
        
        # Save JobSummary
        summary = JobSummary(
            job_id=job.id,
            total_spend_inr=summary_data.get("total_spend_inr", total_inr),
            total_spend_usd=summary_data.get("total_spend_usd", total_usd),
            top_merchants=summary_data.get("top_merchants", top_merchants),
            anomaly_count=summary_data.get("anomaly_count", anomaly_count),
            narrative=summary_data.get("narrative", ""),
            risk_level=summary_data.get("risk_level", "low")
        )
        db.add(summary)
        
        # 5. Finalise Job
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Pipeline completed successfully for job {job_id_str}")

    except Exception as e:
        logger.exception(f"Unhandled exception in pipeline for job {job_id_str}")
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id_str).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as rollback_err:
            logger.error(f"Failed to save job error status: {str(rollback_err)}")
    finally:
        db.close()
