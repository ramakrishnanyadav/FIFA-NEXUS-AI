"""
backend/tests/benchmark_load.py — Latency and Throughput Load Test Harness

Simulates concurrent clients making requests to the running FastAPI server endpoints
to measure real latency (Mean, P95, P99) and request throughput (RPS).
"""
import os
# Force SQLite fallback mode to match local running uvicorn database
os.environ["POSTGRES_PORT"] = "9999"

import asyncio
import time
import numpy as np
import httpx

# Configurations
import os
BASE_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("API_KEY", "".join(["fifanexus_", "api_key_", "2026"]))
CONCURRENCY = 15
TOTAL_REQUESTS = 300

async def benchmark_endpoint(client: httpx.AsyncClient, name: str, url: str, method: str = "GET", headers: dict = None, json_data: dict = None):
    latencies = []
    success_count = 0
    
    print(f"[START] Starting load test for {name} ({method} {url})...")
    
    # We want to maintain target concurrency
    sem = asyncio.Semaphore(CONCURRENCY)
    
    async def make_request():
        async with sem:
            start_time = time.perf_counter()
            try:
                if method == "POST":
                    resp = await client.post(url, headers=headers, json=json_data)
                else:
                    resp = await client.get(url, headers=headers)
                
                duration = (time.perf_counter() - start_time) * 1000.0  # in ms
                if resp.status_code in [200, 201, 202]:
                    latencies.append(duration)
                    return True
                else:
                    print(f"[DIAGNOSTIC] Request failed with status {resp.status_code}: {resp.text[:100]}")
                    return False
            except Exception as e:
                print(f"[DIAGNOSTIC] Request raised exception: {e}")
                return False

    start_bench = time.perf_counter()
    tasks = [make_request() for _ in range(TOTAL_REQUESTS)]
    results = await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - start_bench
    
    success_count = sum(1 for r in results if r)
    
    if not latencies:
        print(f"[FAIL] Load test for {name} failed: 0 successful requests.")
        return None
        
    latencies = np.array(latencies)
    mean_lat = np.mean(latencies)
    p95_lat = np.percentile(latencies, 95)
    p99_lat = np.percentile(latencies, 99)
    rps = success_count / total_duration
    
    print(f"=== {name} Results ===")
    print(f"  - Total Requests: {TOTAL_REQUESTS} (Concurrency: {CONCURRENCY})")
    print(f"  - Success Rate: {success_count}/{TOTAL_REQUESTS} ({success_count/TOTAL_REQUESTS*100:.1f}%)")
    print(f"  - Throughput: {rps:.2f} req/sec")
    print(f"  - Mean Latency: {mean_lat:.2f} ms")
    print(f"  - P95 Latency: {p95_lat:.2f} ms")
    print(f"  - P99 Latency: {p99_lat:.2f} ms")
    print("-" * 50)
    
    return {
        "mean": mean_lat,
        "p95": p95_lat,
        "p99": p99_lat,
        "rps": rps,
        "success": success_count,
        "total": TOTAL_REQUESTS
    }

async def main():
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check if server is running
        try:
            health_check = await client.get(f"{BASE_URL}/health")
            if health_check.status_code != 200:
                raise RuntimeError("Health check returned status code other than 200")
        except Exception:
            print(f"[ERROR] FastAPI server is not running at {BASE_URL}. Run 'uvicorn backend.app.main:app' first.")
            return

        # Fetch a real zone ID from the zones API
        zone_id = None
        try:
            zones_resp = await client.get(f"{BASE_URL}/api/v1/zones")
            if zones_resp.status_code == 200:
                zones = zones_resp.json()
                if zones:
                    zone_id = zones[0]["id"]
                    print(f"[CONFIG] Found active zone '{zones[0]['name']}' with ID: {zone_id}")
                else:
                    print("[ERROR] No zones returned from API. Please run the server with ENVIRONMENT=development to seed zones.")
                    return
            else:
                print(f"[ERROR] Failed to fetch zones from API, status code: {zones_resp.status_code}, response: {zones_resp.text}")
                return
        except Exception as e:
            print(f"[ERROR] Error connecting to zones API: {e}")
            return

        # JSON payload for telemetry endpoint using real zone ID
        telemetry_payload = {
            "zone_id": zone_id,
            "sensor_type": "camera",
            "count": 450,
            "timestamp": "2026-07-08T06:00:00Z"
        }

        # 1. Benchmark health check endpoint
        await benchmark_endpoint(client, "GET /health", f"{BASE_URL}/health")
        
        # 2. Benchmark telemetry ingestion endpoint
        await benchmark_endpoint(
            client, 
            "POST /api/v1/telemetry", 
            f"{BASE_URL}/api/v1/telemetry", 
            method="POST", 
            headers=headers, 
            json_data=telemetry_payload
        )

if __name__ == "__main__":
    asyncio.run(main())
