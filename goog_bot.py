import os
import json
import requests

API_KEY = os.environ.get("SDOT_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

FEED_TYPES = ["roadevent", "workzone", "incident"]
BASE_URL = "https://seattle.gov"

def check_feeds():
    if not API_KEY or not WEBHOOK_URL:
        print("❌ Configuration Error: Missing API keys or Webhook variables.")
        return

    headers = {"Content-Type": "application/json", "X-Api-Key": API_KEY}

    for feed_type in FEED_TYPES:
        print(f"🔬 Testing feed stream layout for: {feed_type}...")
        url = f"{BASE_URL}?type={feed_type}"
        
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

        if events and len(events) > 0:
            print(f"✅ Found data items inside {feed_type}! Sending a sample layout to Discord...")
            
            # Grab the very first item to see how the city builds its data structure
            sample_item = events[0]
            
            # Format a message displaying the raw structure fields to your channel
            payload = {
                "username": "Waze Script Debugger",
                "content": f"🛠️ **Diagnostic Sample Found for `{feed_type}`!** Here is how the city structures this record:\n```json\n{json.dumps(sample_item, indent=2)[:1800]}\n```"
            }
            
            try:
                requests.post(WEBHOOK_URL, json=payload, timeout=10)
                print("📬 Diagnostic sample posted to Discord successfully.")
            except Exception as cb_err:
                print(f"Failed posting debug payload to Discord: {cb_err}")
            
            # Stop after finding one match so we don't spam your Discord server
            return
        else:
            print(f"ℹ️ Feed stream {feed_type} returned data, but the event list is completely empty right now.")

    print("🏁 Debug run finished processing.")

if __name__ == "__main__":
    check_feeds()
