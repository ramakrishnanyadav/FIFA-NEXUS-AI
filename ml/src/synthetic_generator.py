import time
import requests
import random
import sys
from datetime import datetime

BACKEND_URL = "http://localhost:8000/api/v1"

def run_generator():
    print("Starting synthetic telemetry generator for FIFA Nexus AI...")
    
    # 1. Fetch Zones from backend
    try:
        # We fetch via listing endpoint or seed values directly
        # Let's hit the health check first to ensure backend is online
        res = requests.get("http://localhost:8000/health", timeout=5)
        if res.status_code != 200:
            print("Backend health check failed. Ensure the FastAPI application is running on port 8000.")
            sys.exit(1)
    except Exception as e:
        print(f"Failed to connect to backend: {e}. Ensure server is running on localhost:8000")
        sys.exit(1)

    # Fetch zones from DB via custom GET or metadata. Since we seeded Hard Rock Stadium:
    # Let's register a dedicated script-run sequence.
    # To be safe, we will fetch zones from the backend list if we expose a zones endpoint.
    # Wait, we haven't exposed a zones endpoint yet. Let's register a quick endpoint in backend or query DB.
    # Alternatively, the telemetry ingestion endpoint accepts zone_id. We can query the database directly in python 
    # to find zone IDs, or we can look up the seeded zones.
    # Let's write a lookup in PostgreSQL using psycopg2/asyncpg or standard sqlalchemy inside the script, 
    # or expose a GET /api/v1/zones in our backend. Exposing GET /api/v1/zones is very useful for the frontend too!
    # Let's write the generator to assume we can GET /api/v1/zones or fallback to a known seeded list.
    # To keep it simple, let's query the zones endpoint. We will write the GET zones endpoint next.
    
    print("Seeding telemetry ticks...")
    try:
        zones_res = requests.get("http://localhost:8000/api/v1/zones", timeout=5)
        if zones_res.status_code == 200:
            zones = zones_res.json()
        else:
            print(f"Failed to list zones: {zones_res.text}")
            return
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    if not zones:
        print("No zones returned by backend. Ensure DB is seeded.")
        return

    print(f"Found {len(zones)} zones in stadium database. Starting streaming telemetry simulation...")
    
    # Run a simulation loop that escalates occupancy at "Gate A" to trigger an alert
    gate_a = next((z for z in zones if z["name"] == "Gate A"), zones[0])
    safe_capacity = gate_a["safe_capacity"]
    
    # Telemetry steps
    occupancy_steps = [
        int(safe_capacity * 0.4), # 480
        int(safe_capacity * 0.55), # 660
        int(safe_capacity * 0.72), # 864
        int(safe_capacity * 0.85), # 1020 -> Breach! (> 80%)
        int(safe_capacity * 0.95), # 1140
    ]
    
    for i, count in enumerate(occupancy_steps):
        payload = {
            "zone_id": gate_a["id"],
            "sensor_type": "camera",
            "count": count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        print(f"\n[Tick {i+1}/5] Posting telemetry: Zone: {gate_a['name']}, Count: {count}/{safe_capacity} ({(count/safe_capacity)*100:.1f}%)")
        try:
            res = requests.post(f"{BACKEND_URL}/telemetry", json=payload, timeout=5)
            if res.status_code == 202:
                print(f"Response: {res.json()}")
            else:
                print(f"Error: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Post failed: {e}")
            
        time.sleep(2) # 2 seconds interval

if __name__ == "__main__":
    run_generator()
