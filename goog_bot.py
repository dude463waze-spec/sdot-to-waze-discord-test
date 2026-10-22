import os
import json
import requests

API_KEY = os.environ.get("SDOT_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SEEN_FILE = "goog_seen_ids.txt"

FEED_TYPES = ["roadevent", "workzone", "incident"]
BASE_URL = "https://rowimpacts.adc.seattle.gov/api/v1/feed"

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
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": API_KEY
    }

    for feed_type in FEED_TYPES:
        url = f"{BASE_URL}?type={feed_type}"
        print(f"🔬 Connecting to SDOT API Stream: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue
            data = response.json()
        except Exception as e:
            print(f"Skipping {feed_type} stream due to extraction error: {e}")
            continue

        events = data.get("features", []) if isinstance(data, dict) else []
        print(f"📊 Live items found inside {feed_type}: {len(events)}")

        for item in events:
            event_id = str(item.get("id", hash(json.dumps(item))))

            if event_id in seen_ids:
                continue

            properties = item.get("properties", {})
            core_details = properties.get("core_details", {})
            raw_desc = core_details.get("description", {})

            # 1. CLEAN DESCRIPTION PARSING & EXTRACTION
            desc_text = ""
            permit_num = "N/A"
            
            if isinstance(raw_desc, dict):
                desc_text = str(raw_desc.get("PermittedUseDesc", "")).strip()
                permit_num = raw_desc.get("PermitNumber", "N/A")
            else:
                desc_text = str(raw_desc).strip()

            # CRITICAL REFINE: If description text is totally empty, discard immediately
            if not desc_text or desc_text.lower() in ["none", "null", "n/a", ""]:
                new_seen_ids.add(event_id)
                continue

            # 2. LOCATION PARSING & CLEANING
            road_names = core_details.get("road_names", [])
            # Clean out empty strings or random spacing commas from list data
            clean_roads = [r.strip() for r in road_names if r and r.strip() and r.strip() != ","]
            
            if clean_roads:
                location = ", ".join(clean_roads)
            else:
                location = properties.get("location_description", properties.get("location", "")).strip()

            # CRITICAL REFINE: Skip entries with zero actionable location text strings
            if not location or location in [",", "", "Seattle Area"]:
                new_seen_ids.add(event_id)
                continue

            # 3. CONTEXTUAL KEYWORD TRACKING
            # We look for 'all-lanes-closed' explicitly inside the public descriptive fields
            search_block = f"{desc_text} {location} {json.dumps(properties.get('restrictions', []))}".lower()

            if "all-lanes-closed" in search_block:
                
                # WAZE SYSTEM FILTER: Skip non-vehicular closures (sidewalks, transit, bikes)
                skip_keywords = ["sidewalk", "bike lane", "parking lane", "bus stop", "pedestrian"]
                if any(skip_word in search_block for skip_word in skip_keywords):
                    new_seen_ids.add(event_id)
                    continue

                print(f"🚨 REFINED VEHICULAR CLOSURE MATCH: {event_id}")
                
                display_desc = f"**Permit:** {permit_num} — {desc_text}" if permit_num != "N/A" else desc_text
                start_time = properties.get("start_date", "Not specified")
                end_time = properties.get("end_date", "Ongoing")

                payload = {
                    "username": "Waze Seattle Closure Sync",
                    "embeds": [{
                        "title": "⛔ Waze Map Action Required: Full Road Closure",
                        "description": f"**Details:** {display_desc}\n**Impacted Location:** `{location}`",
                        "fields": [
                            {"name": "⏰ Start Time", "value": f"`{start_time}`", "inline": True},
                            {"name": "🏁 End Time", "value": f"`{end_time}`", "inline": True},
                            {"name": "📁 Feed Origin", "value": f"`{feed_type}`", "inline": True}
                        ],
                        "color": 1658035, 
                        "footer": {"text": f"SDOT Feature Reference ID: {event_id}"}
                    }]
                }

                try:
                    requests.post(WEBHOOK_URL, json=payload, timeout=10)
                except Exception as cb_err:
                    print(f"Failed routing webhook message to Discord: {cb_err}")

            new_seen_ids.add(event_id)

    save_seen_ids(new_seen_ids)
    print("✅ Finished processing all city feeds successfully.")

if __name__ == "__main__":
    check_feeds()
