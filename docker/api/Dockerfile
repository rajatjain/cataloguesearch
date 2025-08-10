# Use Python 3.11 as base image
# --- Stage 1: Builder ---
# This stage installs all build-time dependencies and Python packages.
FROM python:3.11-slim AS builder

WORKDIR /app

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
    gcc \
    g++ \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies (this layer will be cached unless requirements.txt changes)
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
# This stage creates the final, smaller runtime image by copying
# only the necessary artifacts from the builder stage.
FROM python:3.11-slim

WORKDIR /app

# Install only the RUNTIME system dependencies (no build tools)
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
    && rm -rf /var/lib/apt/lists/*

# Copy the installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Indic NLP resources from the local directory into the image
COPY indic_nlp_resources /app/indic_nlp_resources
COPY backend/ ./backend/
COPY configs/ ./configs/
COPY utils/ ./utils/

# Copy and set up entrypoint script
COPY docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy the ONNX models into the image from the build context
COPY models/ /app/models/

# Set environment variables
ENV PYTHONPATH=/app

# Expose port for API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/metadata || exit 1

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command to run the API server
CMD ["uvicorn", "backend.api.search_api:app", "--host", "0.0.0.0", "--port", "8000"]
