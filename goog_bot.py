import os
import json
import requests

API_KEY = os.environ.get("SDOT_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
# Renamed tracking file so it stays unique to this project
SEEN_FILE = "goog_seen_ids.txt"

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
        print(f"Checking feed type: {feed_type}...")
        try:
            response = requests.get(f"{BASE_URL}?type={feed_type}", headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ City server replied with status {response.status_code}. Skipping.")
                continue
            data = response.json()
        except Exception as e:
            print(f"Skipping {feed_type} due to error: {e}")
            continue

        events = data if isinstance(data, list) else data.get("items", [])

        for event in events:
            event_id = str(event.get("id") or event.get("uuid") or event.get("incidentId") or hash(json.dumps(event)))

            if event_id in seen_ids:
                continue

            event_string = json.dumps(event).lower()

            if "all-lanes-closed" in event_string:
                description = event.get("description", "").lower()
                
                # Waze Filter: Skip closures that do not block vehicular lanes
                skip_keywords = ["sidewalk", "bike lane", "parking lane", "bus stop", "pedestrian"]
                if any(skip_word in description for skip_word in skip_keywords):
                    new_seen_ids.add(event_id)
                    continue

                print(f"🚨 VEHICULAR CLOSURE MATCH: {event_id}")
                
                display_desc = event.get("description", "No description text provided.")
                location = event.get("location", "Unknown Location")
                start_time = event.get("startTime", "Not specified")
                end_time = event.get("endTime", "Not specified")

                payload = {
                    "username": "Waze Seattle Closure Sync",
                    "embeds": [{
                        "title": "⛔ Waze Map Action: All Lanes Closed",
                        "description": f"**Details:** {display_desc}\n**Location:** {location}",
                        "fields": [
                            {"name": "⏰ Start Time", "value": f"`{start_time}`", "inline": True},
                            {"name": "🏁 End Time", "value": f"`{end_time if end_time else 'Ongoing'}`", "inline": True},
                            {"name": "📁 Source Feed", "value": f"`{feed_type}`", "inline": True}
                        ],
                        "color": 1658035, # Waze blue
                        "footer": {"text": f"SDOT Reference ID: {event_id}"}
                    }]
                }

                try:
                    requests.post(WEBHOOK_URL, json=payload, timeout=10)
                except Exception as cb_err:
                    print(f"Failed posting to Discord: {cb_err}")

            new_seen_ids.add(event_id)

    save_seen_ids(new_seen_ids)
    print("✅ Finished processing all city feeds successfully.")

if __name__ == "__main__":
    check_feeds()
