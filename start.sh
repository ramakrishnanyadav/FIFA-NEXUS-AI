#!/bin/bash
# start.sh — FIFA Nexus AI production startup script
# Starts ML inference service in background, then FastAPI in foreground.
# Compatible with Render free tier (single-process constraint bypassed via &).

set -e

echo "🚀 FIFA Nexus AI — Starting services..."

# Launch ML inference service (port 8001) in background
echo "  [1/2] Starting ML Inference Service on port 8001..."
ML_HOST=127.0.0.1 python -m ml.src.inference &
ML_PID=$!
echo "  [1/2] ML Inference started (PID: $ML_PID)"

# Small delay to let ML service initialize and load LightGBM model
sleep 2

# Launch FastAPI backend in foreground — Render injects $PORT, fallback to 8000
echo "  [2/2] Starting FastAPI backend on port ${PORT:-8000}..."
exec python -m uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --loop asyncio
