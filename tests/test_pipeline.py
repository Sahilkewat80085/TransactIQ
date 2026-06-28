import datetime
from app.services.pipeline import parse_date_robust, clean_amount, generate_stable_txn_id

def test_parse_date_robust():
    assert parse_date_robust("04-09-2024") == datetime.date(2024, 9, 4)
    assert parse_date_robust("2024/02/05") == datetime.date(2024, 2, 5)
    assert parse_date_robust("2024-07-15") == datetime.date(2024, 7, 15)

def test_clean_amount():
    assert clean_amount("10882.55") == 10882.55
    assert clean_amount("$11325.79") == 11325.79
    assert clean_amount("  $11325.79  ") == 11325.79
    assert clean_amount("") == 0.0
    assert clean_amount(None) == 0.0

def test_generate_stable_txn_id():
    row = {"date": "2024-09-04", "merchant": "Flipkart", "amount": 10882.55, "account_id": "ACC003"}
    id1 = generate_stable_txn_id(row, 1)
    id2 = generate_stable_txn_id(row, 1)
    id3 = generate_stable_txn_id(row, 2)
    
    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("TXN_GEN_")
    assert len(id1) == 16  # TXN_GEN_ (8 chars) + MD5 slice (8 chars)

def test_anomaly_detection_logic():
    # Simulate anomaly checks on test transactions
    medians = {"ACC001": 100.0, "ACC002": 50.0}
    domestic_brands = ['swiggy', 'ola', 'irctc', 'zomato', 'jio recharge', 'bigbasket', 'blinkit', 'nykaa', 'meesho']
    
    def check_anomaly(amount, account_id, currency, merchant):
        is_anomaly = False
        reasons = []
        
        # Rule 1
        median_val = medians.get(account_id, 0.0)
        if amount > 3 * median_val:
            is_anomaly = True
            reasons.append("Statistical outlier: amount exceeds 3x account median")
            
        # Rule 2
        if currency == 'USD' and merchant.lower() in domestic_brands:
            is_anomaly = True
            reasons.append("Currency anomaly: USD used with domestic-only merchant")
            
        return is_anomaly, "; ".join(reasons) if is_anomaly else None

    # Case 1: Standard transaction
    is_anom, reason = check_anomaly(150.0, "ACC001", "INR", "Amazon")
    assert not is_anom
    assert reason is None
    
    # Case 2: Rule 1 anomaly (amount > 3 * median)
    is_anom, reason = check_anomaly(350.0, "ACC001", "INR", "Amazon")
    assert is_anom
    assert "Statistical outlier" in reason
    
    # Case 3: Rule 2 anomaly (USD + domestic merchant)
    is_anom, reason = check_anomaly(20.0, "ACC001", "USD", "Swiggy")
    assert is_anom
    assert "Currency anomaly" in reason
    
    # Case 4: Both anomalies combined
    is_anom, reason = check_anomaly(400.0, "ACC001", "USD", "Swiggy")
    assert is_anom
    assert "Statistical outlier" in reason
    assert "Currency anomaly" in reason

def test_sanitize_string():
    from app.services.pipeline import sanitize_string
    
    # Test script tags removal
    assert "alert('xss')" in sanitize_string("Hello <script>alert('xss')</script> World")
    assert "<script>" not in sanitize_string("Hello <script>alert('xss')</script> World")
    # Test javascript protocol removal
    assert "javascript:" not in sanitize_string("javascript:alert(1)")
    # Test event handlers removal
    assert "onerror" not in sanitize_string("<img src=x onerror=alert(1)>")
    # Test clean input remains untouched
    assert sanitize_string("Clean transaction notes") == "Clean transaction notes"
