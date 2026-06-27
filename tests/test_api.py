from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "TransactIQ API"
    assert response.json()["status"] == "running"

def test_upload_validation_non_csv():
    files = {"file": ("test.txt", b"some dummy data", "text/plain")}
    response = client.post("/jobs/upload", files=files)
    assert response.status_code == 400
    assert "Only CSV files are allowed" in response.json()["detail"]

def test_upload_validation_oversized():
    # 10MB + 10 bytes file
    files = {"file": ("test.csv", b"a" * (10 * 1024 * 1024 + 10), "text/csv")}
    response = client.post("/jobs/upload", files=files)
    assert response.status_code == 400
    assert "File size exceeds maximum limit of 10MB" in response.json()["detail"]

def test_upload_validation_missing_headers():
    files = {"file": ("test.csv", b"txn_id,date,merchant\nTXN001,2024-01-01,Flipkart\n", "text/csv")}
    response = client.post("/jobs/upload", files=files)
    assert response.status_code == 400
    assert "Missing required columns" in response.json()["detail"]

@patch("app.routes.jobs.process_csv_task.delay")
def test_successful_upload(mock_celery_delay):
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    csv_data = b"txn_id,date,merchant,amount,currency,status,category,account_id,notes\nTXN101,2024-01-01,Zomato,250.0,INR,SUCCESS,Food,ACC01,verified\n"
    files = {"file": ("transactions.csv", csv_data, "text/csv")}
    
    response = client.post("/jobs/upload", files=files)
    
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert "job_id" in response.json()
    mock_celery_delay.assert_called_once()
    
    app.dependency_overrides.clear()

def test_list_jobs():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
    app.dependency_overrides.clear()
