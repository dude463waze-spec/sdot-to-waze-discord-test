import os
import json
import requests
from datetime import datetime, timedelta

API_KEY = os.environ.get("SDOT_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

FEED_TYPES = ["roadevent", "workzone", "incident"]
BASE_URL = "https://seattle.gov"

def check_feeds():
    if not API_KEY or not WEBHOOK_URL:
        print("❌ Configuration Error: Missing API keys or Webhook variables.")
        return

    headers = {"Content-Type": "application/json", "X-Api-Key": API_KEY}
    
    # Calculate 30 days ago to filter out ancient history
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    for feed_type in FEED_TYPES:
        print(f"🔬 Fetching historical 30-day stream for: {feed_type}...")
        
        # Added status=all to force the API to give us historical/closed items, not just live ones
        url = f"{BASE_URL}?type={feed_type}&status=all"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Feed responded with status: {response.status_code}")
                continue
                
            data = response.json()
        except Exception as e:
            print(f"Skipping {feed_type} due to connection error: {e}")
            continue

        events = []
        if isinstance(data, dict):
            events = data.get("features", data.get("items", []))
        elif isinstance(data, list):
            events = data

        print(f"Total raw items returned from city for {feed_type}: {len(events)}")

        # Look through the events to find a sample from the last 30 days
        for item in events:
            properties = item.get("properties", item) if isinstance(item, dict) else {}
            
            # WZDx date fields can vary, so we check common ones
            start_str = properties.get("start_date", properties.get("startTime", ""))
            
            # Try to see if this item is relatively recent
            is_recent = True
            if start_str:
                try:
                    # Clean up common ISO timestamp formats to check the date
                    clean_date = start_str.split("T")[0]
                    item_date = datetime.strptime(clean_date, "%Y-%m-%d")
                    if item_date < thirty_days_ago:
                        is_recent = False  # Skip if it's older than 30 days
                except:
                    pass # If date parsing fails, keep it anyway just to test

            if is_recent:
                print(f"✅ Found a valid sample item in {feed_type}! Pushing layout to Discord...")
                
                payload = {
                    "username": "Waze Historical Tester",
                    "content": f"📦 **Success! Connection verified.** Here is a sample record from the `{feed_type}` feed:\n```json\n{json.dumps(item, indent=2)[:1800]}\n```"
                }
                
                try:
                    requests.post(WEBHOOK_URL, json=payload, timeout=10)
                    print("📬 Sample successfully pushed to your Discord channel.")
                    return  # Stop the script immediately after one successful test post
                except Exception as cb_err:
                    print(f"Failed posting payload to Discord: {cb_err}")

    print("🏁 Lookback run finished processing.")

if __name__ == "__main__":
    check_feeds()
