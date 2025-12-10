# trade-agent Dockerfile
# Python agent for real-time trading with LangGraph pipeline

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (needed for some ML packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY main.py ./

# Create directories
RUN mkdir -p /app/data /app/models /app/logs

# Environment variables - Core
ENV TRADING_MODE=fast
ENV DRY_RUN=true
ENV SQLITE_PATH=/app/data/user_data.db
ENV API_BASE_URL=http://nuahchain-backend:8080
ENV DATA_DIR=/app/data

# Environment variables - Fast Mode
ENV PRICE_POLL_INTERVAL_SECONDS=5
ENV DECISION_INTERVAL_SECONDS=15
ENV STOP_LOSS_PERCENT=0.10
ENV TRAILING_STOP_PERCENT=0.08
ENV TAKE_PROFIT_PERCENT=0.25
ENV EMERGENCY_EXIT_THRESHOLD=-0.30
ENV RUG_THRESHOLD_1M=-0.50
ENV PUMP_THRESHOLD_1M=0.05
ENV DUMP_THRESHOLD_1M=-0.10
ENV VOLUME_SPIKE_THRESHOLD=3.0

# Environment variables - Gemini Scam Detection
ENV ENABLE_TOKEN_ANALYZER=true
ENV GEMINI_MODEL=gemini-2.0-flash
ENV TOKEN_ANALYZER_CACHE_TTL=300

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=10s --retries=3 \
    CMD python -c "import src; print('healthy')" || exit 1

# Run the trade agent
CMD ["python", "main.py"]

