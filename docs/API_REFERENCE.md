# API Reference

All endpoints are prefixed with `/api/v1`. Endpoints that write data require a valid `X-API-Key` header.

## Authentication

All write operations must include the API key header:
- Header: `X-API-Key: fifanexus_api_key_2026`

---

## Endpoints

### 1. Health Status
`GET /health`
- **Description**: Returns server, database, Redis cache, and API key configuration status.
- **Response (200)**:
  ```json
  {
    "status": "healthy",
    "service": "FIFA Nexus AI",
    "database": "postgresql",
    "redis": "online",
    "api_key_configured": true
  }
  ```

### 2. Telemetry Ingestion
`POST /api/v1/telemetry`
- **Security**: Required `X-API-Key`
- **Description**: Ingest turnstile or camera counts for a specific zone.
- **Request Body**:
  ```json
  {
    "zone_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "sensor_type": "camera",
    "count": 450,
    "timestamp": "2026-07-08T06:00:00Z"
  }
  ```
- **Response (202)**:
  ```json
  {
    "status": "success",
    "event_triggered": "CROWD_DENSITY_HIGH",
    "recommendation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }
  ```

### 3. List Zones
`GET /api/v1/zones`
- **Description**: List all stadium zones, capacities, and live occupancy counts.
- **Response (200)**:
  ```json
  [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "Gate A",
      "zone_type": "GATE",
      "safe_capacity": 1200,
      "current_occupancy": 850
    }
  ]
  ```

### 4. Apply AI Recommendation
`POST /api/v1/recommendations/{id}/apply`
- **Security**: Required `X-API-Key`
- **Description**: Approve an optimized recommendation and dispatch tasks to the ground.
- **Response (200)**:
  ```json
  {
    "status": "dispatched",
    "tasks_created": 3
  }
  ```

### 5. Chat Operations Assistant
`POST /api/v1/assistant/chat`
- **Security**: Required `X-API-Key`
- **Description**: Query live metrics, green sustainability goals, or procedures.
- **Request Body**:
  ```json
  {
    "message": "Where is the fastest entrance?"
  }
  ```
- **Response (200)**:
  ```json
  {
    "response": "Fan Navigation: The fastest entrance is currently Gate B...",
    "intent": "fan_navigation"
  }
  ```

### 6. Recommendations Metrics & Analytics
`GET /api/v1/recommendations/stats`
- **Description**: Retrieve live statistics, validation pass rates, provider usage, and cumulative carbon savings.
- **Response (200)**:
  ```json
  {
    "total_count": 8,
    "avg_reasoning_time_ms": 142.5,
    "validated_count": 7,
    "violation_count": 1,
    "total_co2_saved_kg": 24.3,
    "provider_stats": {
      "openai/gpt-4o": 6,
      "groq/llama-3.1-70b": 2
    }
  }
  ```

