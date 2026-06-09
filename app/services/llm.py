import json
import time
import logging
from typing import List, Dict, Any
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY is not set. LLM calls will fail unless configured.")

def get_model():
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={"response_mime_type": "application/json"}
    )

def call_llm_with_retry(prompt: str, retries: int = 3, initial_delay: float = 2.0) -> str:
    """Calls the LLM with exponential backoff retry logic."""
    model = get_model()
    delay = initial_delay
    
    for attempt in range(retries + 1):
        try:
            logger.info(f"Calling LLM, attempt {attempt + 1}")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if attempt == retries:
                logger.error(f"LLM call failed after {retries} retries: {str(e)}")
                raise e
            logger.warning(f"LLM call failed: {str(e)}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2.0  # Exponential backoff

def classify_categories_batch(transactions: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Classifies a batch of transactions into categories using the LLM.
    Returns a dictionary mapping txn_id to category.
    """
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "dummy_gemini_api_key_or_replace_me":
        logger.warning("Using mock classification because Gemini API Key is not set or dummy.")
        # Fallback to mock classification based on merchant names
        mock_map = {}
        for txn in transactions:
            merchant = str(txn.get("merchant", "")).lower()
            txn_id = txn.get("txn_id")
            if "swiggy" in merchant or "zomato" in merchant:
                mock_map[txn_id] = "Food"
            elif "amazon" in merchant or "flipkart" in merchant or "nykaa" in merchant or "meesho" in merchant:
                mock_map[txn_id] = "Shopping"
            elif "irctc" in merchant or "makemytrip" in merchant:
                mock_map[txn_id] = "Travel"
            elif "ola" in merchant:
                mock_map[txn_id] = "Transport"
            elif "jio" in merchant:
                mock_map[txn_id] = "Utilities"
            elif "bookmyshow" in merchant:
                mock_map[txn_id] = "Entertainment"
            elif "atm" in merchant:
                mock_map[txn_id] = "Cash Withdrawal"
            else:
                mock_map[txn_id] = "Other"
        return mock_map

    prompt = f"""
You are a financial transaction classifier. Given a JSON list of transaction objects, classify each transaction into one of these exact categories: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other.

Return a JSON object mapping each transaction's 'txn_id' to its classified category. Do not return any other text, only the JSON object.

Transactions to classify:
{json.dumps(transactions, indent=2)}
"""
    try:
        response_text = call_llm_with_retry(prompt)
        result = json.loads(response_text)
        return result
    except Exception as e:
        logger.error(f"Error in batch classification: {str(e)}")
        raise e

def generate_narrative_summary(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a spending narrative and risk level assessment using the LLM based on aggregate stats.
    """
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "dummy_gemini_api_key_or_replace_me":
        logger.warning("Using mock narrative summary because Gemini API Key is not set or dummy.")
        # Return mock data
        risk = "low"
        if stats.get("anomaly_count", 0) > 3:
            risk = "high"
        elif stats.get("anomaly_count", 0) > 0:
            risk = "medium"
        return {
            "total_spend_inr": stats.get("total_spend_inr", 0.0),
            "total_spend_usd": stats.get("total_spend_usd", 0.0),
            "top_merchants": stats.get("top_merchants", []),
            "anomaly_count": stats.get("anomaly_count", 0),
            "narrative": f"Spending analysis shows primary activity at {', '.join(stats.get('top_merchants', [])[:2])}. Total spend reached {stats.get('total_spend_inr', 0.0):,.2f} INR and {stats.get('total_spend_usd', 0.0):,.2f} USD. A total of {stats.get('anomaly_count', 0)} anomalies were flagged during processing.",
            "risk_level": risk
        }

    prompt = f"""
You are a financial risk analyst. Analyze the following aggregated transaction statistics and generate a 2-3 sentence narrative describing the spending patterns and any notable anomalies. Also assign an overall risk level (low, medium, or high) based on the presence and severity of anomalies or suspicious notes.

Statistics:
{json.dumps(stats, indent=2)}

Return a JSON object with exactly these keys:
- total_spend_inr (float: copy the provided total spend in INR)
- total_spend_usd (float: copy the provided total spend in USD)
- top_merchants (list of strings: copy or refine the top merchants list)
- anomaly_count (int: copy the provided anomaly count)
- narrative (string: 2-3 sentences spending narrative)
- risk_level (string: "low", "medium", or "high")
"""
    try:
        response_text = call_llm_with_retry(prompt)
        result = json.loads(response_text)
        return result
    except Exception as e:
        logger.error(f"Error in narrative generation: {str(e)}")
        # Return fallback structured data in case of error
        return {
            "total_spend_inr": stats.get("total_spend_inr", 0.0),
            "total_spend_usd": stats.get("total_spend_usd", 0.0),
            "top_merchants": stats.get("top_merchants", []),
            "anomaly_count": stats.get("anomaly_count", 0),
            "narrative": "Spending analysis fallback. Spend is concentrated in INR and USD. Outliers detected.",
            "risk_level": "medium"
        }
