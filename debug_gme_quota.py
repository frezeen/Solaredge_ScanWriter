import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load env
load_dotenv()

username = os.getenv('GME_USERNAME')
password = os.getenv('GME_PASSWORD')
base_url = "https://api.mercatoelettrico.org/request/api/v1"

print(f"--- GME API Debug ---")
print(f"Username: {username}")
print(f"Base URL: {base_url}")

if not username or not password:
    print("❌ Missing credentials in .env")
    exit(1)

session = requests.Session()
session.headers.update({
    'User-Agent': 'SolarEdge-ScanWriter/1.0',
    'Accept': 'application/json'
})

# 1. Authentication
print("\n[1] Authenticating...")
auth_url = f"{base_url}/Auth"
payload = {"Login": username, "Password": password}

try:
    response = session.post(auth_url, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        if token:
            print("[OK] Authentication successful. Token received.")
            session.headers.update({'Authorization': f"Bearer {token}"})
        else:
            print("[X] Token not found in response.")
            print(response.text)
            exit(1)
    else:
        print(f"[X] Authentication failed: {response.text}")
        exit(1)

except Exception as e:
    print(f"[X] Auth Error: {e}")
    exit(1)

# 2. Check Quota Status
print("\n[2] Checking Quota Status (GetMyQuotas)...")
quota_url = f"{base_url}/GetMyQuotas"

try:
    response = session.get(quota_url, timeout=30)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        quota_data = response.json()
        print("[OK] Quota data retrieved successfully.\n")
        
        # Display current usage
        print("=== CURRENT USAGE ===")
        print(f"Last Modified Time:       {quota_data.get('LastModifiedTime', 'N/A')}")
        print(f"Last Modified Hour:       {quota_data.get('LastModifiedHour', 'N/A')}")
        print(f"Active Connections:       {quota_data.get('ActiveConnections', 0)}")
        print(f"Connections Per Minute:   {quota_data.get('ConnectionsPerMinute', 0)}")
        print(f"Connections Per Hour:     {quota_data.get('ConnectionsPerHour', 0)}")
        print(f"Data Per Minute:          {quota_data.get('DataPerMinute', 0)}")
        print(f"Data Per Hour:            {quota_data.get('DataPerHour', 0)}")
        
        # Display limits
        limits = quota_data.get('Limits', {})
        if limits:
            print("\n=== QUOTA LIMITS ===")
            print(f"Max Concurrent Connections:   {limits.get('MaxConcurrentConnections', 'N/A')}")
            print(f"Max Connections Per Minute:   {limits.get('MaxConnectionsPerMinute', 'N/A')}")
            print(f"Max Connections Per Hour:     {limits.get('MaxConnectionsPerHour', 'N/A')}")
            print(f"Max Data Per Minute:          {limits.get('MaxDataPerMinute', 'N/A')}")
            print(f"Max Data Per Hour:            {limits.get('MaxDataPerHour', 'N/A')}")
            
            # Calculate usage percentages
            print("\n=== USAGE PERCENTAGES ===")
            conn_hour = quota_data.get('ConnectionsPerHour', 0)
            max_conn_hour = limits.get('MaxConnectionsPerHour', 1)
            data_hour = quota_data.get('DataPerHour', 0)
            max_data_hour = limits.get('MaxDataPerHour', 1)
            
            conn_pct = (conn_hour / max_conn_hour * 100) if max_conn_hour > 0 else 0
            data_pct = (data_hour / max_data_hour * 100) if max_data_hour > 0 else 0
            
            print(f"Connections Used (Hour):  {conn_hour}/{max_conn_hour} ({conn_pct:.1f}%)")
            print(f"Data Used (Hour):         {data_hour}/{max_data_hour} ({data_pct:.1f}%)")
            
            # Warning if approaching limits
            if conn_pct > 80 or data_pct > 80:
                print("\n[!] WARNING: Approaching quota limits!")
        
        print("\n=== RAW JSON ===")
        print(json.dumps(quota_data, indent=2))
        
    else:
        print(f"[X] Quota check failed.")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"[X] Quota Check Error: {e}")

# 3. Make a test data request to see quota impact
print("\n[3] Making Test Data Request (Yesterday)...")
yesterday = datetime.now() - timedelta(days=1)
date_param = yesterday.strftime('%Y%m%d')

req_url = f"{base_url}/RequestData"
req_payload = {
    'Platform': 'PublicMarketResults',
    'Segment': 'MGP',
    'DataName': 'ME_ZonalPrices',
    'IntervalStart': date_param,
    'IntervalEnd': date_param,
    'Attributes': {}
}

try:
    response = session.post(req_url, json=req_payload, timeout=60)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print("[OK] Request successful.")
        data = response.json()
        print(f"Data points received: {len(data) if isinstance(data, list) else 'N/A'}")
    else:
        print(f"[X] Request failed.")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"[X] Request Error: {e}")

# 4. Check quota again after request
print("\n[4] Checking Quota After Request...")
try:
    response = session.get(quota_url, timeout=30)
    if response.status_code == 200:
        quota_data = response.json()
        print(f"Connections Per Hour:  {quota_data.get('ConnectionsPerHour', 0)}")
        print(f"Data Per Hour:         {quota_data.get('DataPerHour', 0)}")
        
        limits = quota_data.get('Limits', {})
        if limits:
            max_data = limits.get('MaxDataPerHour', 1)
            current_data = quota_data.get('DataPerHour', 0)
            remaining = max_data - current_data
            print(f"Remaining Data Quota:  {remaining}/{max_data} ({remaining/max_data*100:.1f}% available)")
    else:
        print(f"[X] Post-request quota check failed: {response.text}")
except Exception as e:
    print(f"[X] Post-request Quota Error: {e}")
