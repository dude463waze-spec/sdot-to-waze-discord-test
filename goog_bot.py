import os
import json
import requests

API_KEY = os.environ.get("SDOT_API_KEY")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SEEN_FILE = "goog_seen_ids.txt"

# Official Backend SDOT Targets - CORRECT ENDPOINT LOCKED
FEED_TYPES = ["roadevent", "workzone", "incident"]
BASE_URL = "https://seattle.gov"

def load_seen_ids():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def append_seen_id(event_id):
    with open(SEEN_FILE, "a") as f:
        f.write(f"{event_id}\n")

def check_feeds():
    if not API_KEY or not WEBHOOK_URL:
        print("❌ Configuration Error: Missing API keys or Webhook variables.")
        return

    seen_ids = load_seen_ids()
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

            # 1. PARSE DESCRIPTION & TRACK TEXT
            desc_text = ""
            permit_num = "N/A"
            if isinstance(raw_desc, dict):
                desc_text = str(raw_desc.get("PermittedUseDesc", "")).strip()
                permit_num = raw_desc.get("PermitNumber", "N/A")
            else:
                desc_text = str(raw_desc).strip()

            if not desc_text or desc_text.lower() in ["none", "null", "n/a", ""]:
                desc_text = str(core_details.get("event_type", "Traffic Obstruction"))

            # 2. PARSE LOCATION
            road_names = core_details.get("road_names", [])
            clean_roads = [r.strip() for r in road_names if r and r.strip() and r.strip() != ","]
            location = ", ".join(clean_roads) if clean_roads else properties.get("location_description", properties.get("location", "")).strip()

            if not location or location in [",", "", "Seattle Area"]:
                seen_ids.add(event_id)
                append_seen_id(event_id)
                continue

            # 3. HARVEST SCATTERED HOURLY SCHEDULE DETAILS (THE MISSING LINK)
            restrictions = properties.get("restrictions", [])
            schedule_notes = []
            
            # Extract hourly windows buried inside the restrictions tracking system
            if isinstance(restrictions, list):
                for r in restrictions:
                    if isinstance(r, dict):
                        # Extract hidden schedule tags used by WZDx
                        time_details = [
                            r.get("scheduled_hours"),
                            r.get("types_of_work"),
                            r.get("restriction_type")
                        ]
                        for detail in time_details:
                            if detail and str(detail).strip() and str(detail) != "None":
                                schedule_notes.append(str(detail))

            # 4. KEYWORD CHECK
            vehicle_impact = str(properties.get("vehicle_impact", "")).lower()
            restrictions_list = json.dumps(restrictions).lower()
            public_text = f"{desc_text} {location}".lower()

            if "all-lanes-closed" in vehicle_impact or "all-lanes-closed" in restrictions_list or "all-lanes-closed" in public_text:
                
                # WAZE VEHICULAR FILTER: Skip sidewalk, bike, and bus lanes
                skip_keywords = ["sidewalk", "bike lane", "parking lane", "bus stop", "pedestrian"]
                if any(skip_word in public_text for skip_word in skip_keywords):
                    seen_ids.add(event_id)
                    append_seen_id(event_id)
                    continue

                print(f"🚨 MATCHED NEW CLOSURE WORK WINDOW: {event_id}")
                
                display_desc = f"**Permit:** {permit_num} — {desc_text}" if permit_num != "N/A" else desc_text
                start_window = properties.get("start_date", "Not specified")
                end_window = properties.get("end_date", "Ongoing")

                # Format the hourly schedule block cleanly for Discord view layouts
                hours_value = "\n".join([f"• {note}" for note in schedule_notes]) if schedule_notes else "`No hourly restrictions specified in feed.`"

                payload = {
                    "username": "Waze Seattle Closure Sync",
                    "embeds": [{
                        "title": "⛔ Waze Map Action Required: Full Road Closure",
                        "description": f"**Details:** {display_desc}\n**Impacted Location:** `{location}`",
                        "fields": [
                            {"name": "⏰ Active Work Schedule / Hours", "value": hours_value, "inline": False},
                            {"name": "📅 Broad Permit Start", "value": f"`{start_window[:10]}`", "inline": True},
                            {"name": "📅 Broad Permit End", "value": f"`{end_window[:10]}`", "inline": True},
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

            seen_ids.add(event_id)
            append_seen_id(event_id)

    print("✅ Finished processing all city feeds successfully.")

if __name__ == "__main__":
    check_feeds()
