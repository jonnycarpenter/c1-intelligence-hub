# C1 Intelligence Hub v2
# All-in-one Cloud Run deployment with Next.js frontend and FastAPI backend

# Stage 1: Build Frontend (Static Export)
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY frontend/ ./

# Build the Next.js application (static export)
RUN npm run build

# Stage 2: Python Backend + Static Frontend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ ./

# Copy static frontend from builder stage (static export goes to 'out' directory)
COPY --from=frontend-builder /app/frontend/out ./frontend/out

# Create necessary directories
RUN mkdir -p /app/logs /app/downloads

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start script to run both frontend and backend
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
