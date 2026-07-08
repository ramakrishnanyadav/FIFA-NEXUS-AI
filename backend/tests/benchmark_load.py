"""
backend/tests/benchmark_load.py — Latency and Throughput Load Test Harness

Simulates concurrent clients making requests to the running FastAPI server endpoints
to measure real latency (Mean, P95, P99) and request throughput (RPS).
"""
import asyncio
import time
import numpy as np
import httpx

# Configurations
BASE_URL = "http://localhost:8000"
API_KEY = "fifanexus_api_key_2026"
CONCURRENCY = 15
TOTAL_REQUESTS = 300

async def benchmark_endpoint(client: httpx.AsyncClient, name: str, url: str, method: str = "GET", headers: dict = None, json_data: dict = None):
    latencies = []
    success_count = 0
    
    print(f"🚀 Starting load test for {name} ({method} {url})...")
    
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
                    return False
            except Exception:
                return False

    start_bench = time.perf_counter()
    tasks = [make_request() for _ in range(TOTAL_REQUESTS)]
    results = await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - start_bench
    
    success_count = sum(1 for r in results if r)
    
    if not latencies:
        print(f"❌ Load test for {name} failed: 0 successful requests.")
        return None
        
    latencies = np.array(latencies)
    mean_lat = np.mean(latencies)
    p95_lat = np.percentile(latencies, 95)
    p99_lat = np.percentile(latencies, 99)
    rps = success_count / total_duration
    
    print(f"📊 {name} Results:")
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
    
    # JSON payload for telemetry endpoint using empty UUID
    telemetry_payload = {
        "zone_id": "00000000-0000-0000-0000-000000000000",
        "sensor_type": "camera",
        "count": 450,
        "timestamp": "2026-07-08T06:00:00Z"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check if server is running
        try:
            health_check = await client.get(f"{BASE_URL}/health")
            if health_check.status_code != 200:
                raise Exception()
        except Exception:
            print(f"❌ Error: FastAPI server is not running at {BASE_URL}. Run 'uvicorn backend.app.main:app' first.")
            return

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
