# ═══════════════════════════════════════════════════════════════
#  CivicPulse Backend — Dockerfile
# ═══════════════════════════════════════════════════════════════
#  Build:  docker build -t civicpulse-backend .
#  Run:    docker run -p 8000:8000 civicpulse-backend
# ═══════════════════════════════════════════════════════════════

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
