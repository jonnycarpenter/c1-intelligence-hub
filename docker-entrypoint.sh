#!/bin/bash
set -e

echo "========================================"
echo "Starting C1 Intelligence Hub v2"
echo "========================================"
echo "Environment: ${ENVIRONMENT:-development}"
echo "Port: ${PORT:-8080}"
echo "Data Dir: ${DATA_DIR:-./data}"
echo ""

# Ensure data directories exist (especially important for GCS mounts)
mkdir -p "${DATA_DIR:-./data}/chroma" 2>/dev/null || true
mkdir -p "${DATA_DIR:-./data}/knowledge_db" 2>/dev/null || true
mkdir -p "${DATA_DIR:-./data}/downloads" 2>/dev/null || true
mkdir -p ./logs 2>/dev/null || true

# Wait for GCS mount to be ready (Cloud Run specific)
if [ "${ENVIRONMENT}" = "production" ]; then
    echo "Waiting for GCS mount..."
    sleep 2
    if [ -d "${DATA_DIR:-/app/data}" ]; then
        echo "GCS mount ready at ${DATA_DIR:-/app/data}"
        ls -la "${DATA_DIR:-/app/data}" || true
    fi
fi

echo ""
echo "Starting FastAPI backend..."

# Start FastAPI backend
# In production: single worker (Cloud Run handles scaling via instances)
# Timeout set high for long-running LLM calls
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers 1 \
    --timeout-keep-alive 75 \
    --limit-concurrency 100
