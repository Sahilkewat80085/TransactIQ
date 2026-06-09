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
