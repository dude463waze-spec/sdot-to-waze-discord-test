import os
import json
import requests

API_KEY = os.environ.get("SDOT_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SEEN_FILE = "goog_seen_ids.txt"

# WZDx standardized base feeds
FEED_TYPES = ["roadevent", "workzone", "incident"]
BASE_URL = "https://seattle.gov"

def load_seen_ids():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_ids(seen_ids):
    with open(SEEN_FILE, "w") as f:
        for cid in sorted(seen_ids):
            f.write(f"{cid}\n")

def check_feeds():
    if not API_KEY or not WEBHOOK_URL:
        print("❌ Configuration Error: Missing API keys or Webhook variables.")
        return

    seen_ids = load_seen_ids()
    new_seen_ids = set(seen_ids)
    headers = {"Content-Type": "application/json", "X-Api-Key": API_KEY}

    for feed_type in FEED_TYPES:
        print(f"Checking WZDx feed stream: {feed_type}...")
        url = f"{BASE_URL}?type={feed_type}"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Feed skipped. Status: {response.status_code}")
                continue
                
            data = response.json()
        except Exception as e:
            print(f"Skipping {feed_type} stream due to connection error: {e}")
            continue

        # Standard WZDx feeds wrap features within a standard GeoJSON list structure
        events = []
        if isinstance(data, dict):
            events = data.get("features", data.get("items", []))
        elif isinstance(data, list):
            events = data

        for item in events:
            # WZDx maps core parameters inside the properties dictionary structure
            properties = item.get("properties", item) if isinstance(item, dict) else {}
            
            # Extract a reliable unique ID string tracking reference
            event_id = str(properties.get("id") or item.get("id") or properties.get("road_event_id") or hash(json.dumps(item)))

            if event_id in seen_ids:
                continue

            # Flatten the item down to scan text block for closure details
            full_item_text = json.dumps(item).lower()

            if "all-lanes-closed" in full_item_text:
                description = (properties.get("description", "") or properties.get("road_event_type", "")).lower()
                
                # WAZE MAPPER FILTER: Proactively bypass blocks that do not impact vehicular lane travel
                skip_keywords = ["sidewalk", "bike lane", "parking lane", "bus stop", "pedestrian"]
                if any(skip_word in description for skip_word in skip_keywords):
                    new_seen_ids.add(event_id)
                    continue

                print(f"🚨 MATCHED VEHICULAR CLOSURE ID: {event_id}")
                
                # Parse structured tracking fields cleanly out of the payload
                display_desc = properties.get("description", "No description text provided.")
                location = properties.get("location_description", properties.get("location", "Unknown Seattle Location"))
                start_time = properties.get("start_date", properties.get("startTime", "Not specified"))
                end_time = properties.get("end_date", properties.get("endTime", "Ongoing"))

                # Format layout for Discord message output look
                payload = {
                    "username": "Waze Seattle Closure Sync",
                    "embeds": [{
                        "title": "⛔ Waze Map Action Required: Full Road Closure",
                        "description": f"**Details:** {display_desc}\n**Location:** {location}",
                        "fields": [
                            {"name": "⏰ Start Time", "value": f"`{start_time}`", "inline": True},
                            {"name": "🏁 End Time", "value": f"`{end_time}`", "inline": True},
                            {"name": "📁 Feed Stream", "value": f"`{feed_type}`", "inline": True}
                        ],
                        "color": 1658035,  # Distinctive Waze theme blue accent
                        "footer": {"text": f"WZDx Reference Token ID: {event_id}"}
                    }]
                }

                try:
                    requests.post(WEBHOOK_URL, json=payload, timeout=10)
                except Exception as cb_err:
                    print(f"Failed posting to Discord webhook server: {cb_err}")

            new_seen_ids.add(event_id)

    save_seen_ids(new_seen_ids)
    print("✅ Completed standard WZDx processing cleanly.")

if __name__ == "__main__":
    check_feeds()
