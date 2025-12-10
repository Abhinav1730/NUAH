# rules-agent Dockerfile
# Python agent for user rules and permissions

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY scheduler.py ./
COPY main.py ./

# Create data directories
RUN mkdir -p /app/data /app/output

# Environment variables
ENV RULES_INTERVAL_MINUTES=5
ENV OPENROUTER_API_KEY=""
ENV RULES_AGENT_DATA_DIR=/app/data
ENV OUTPUT_DIR=/app/output

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python -c "print('healthy')" || exit 1

# Run the scheduler
CMD ["python", "scheduler.py"]

