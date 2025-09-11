import requests
import json

def test_opening_balances():
    url = "http://127.0.0.1:8000/api/transactions/"
    
    # Test data
    data = [{
        "user_company": "Test Company",
        "company": "Test Division",
        "ledger_name": "Test Ledger",
        "opening_balance": "10000.00",
        "group": "Sundry Debtors",
        "raw_balance": "10000.00 Dr",
        "voucher_type": "Opening Balance",
        "register_type": "opening_balance",
        "date": "20250101"
    }]
    
    # Make request
    response = requests.post(url, json=data)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    try:
        print(f"Response Body: {response.json()}")
    except:
        print(f"Raw Response: {response.text}")

if __name__ == "__main__":
    test_opening_balances()
