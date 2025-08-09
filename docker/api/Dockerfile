# Use Python 3.11 as base image
FROM python:3.11-slim

# Install system dependencies for OCR, PDF processing, and compilation
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-guj \
    tesseract-ocr-eng \
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    git \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies (this layer will be cached unless requirements.txt changes)
RUN pip install --no-cache-dir -r requirements.txt && \
    pip cache purge && \
    rm -rf /root/.cache/pip

# Copy only the necessary application code (this invalidates cache when code changes, but deps remain cached)
COPY backend/ ./backend/
COPY configs/ ./configs/
COPY utils/ ./utils/

# Copy and set up entrypoint script
COPY docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create directories for data persistence
RUN mkdir -p /app/data/pdf /app/data/text /app/data/cataloguesearch/db /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV OPENSEARCH_HOST=opensearch
ENV OPENSEARCH_PORT=9200
ENV OPENSEARCH_USERNAME=admin
ENV OPENSEARCH_PASSWORD=Admin@Password123!
ENV LOGS_DIR=/app/logs

# Expose port for API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command to run the API server
CMD ["uvicorn", "backend.api.search_api:app", "--host", "0.0.0.0", "--port", "8000"]