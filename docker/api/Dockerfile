# Use Python 3.11 as base image
# --- Stage 1: Builder ---
# This stage installs all build-time dependencies and Python packages.
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for API only (no OCR/PDF processing)
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy API requirements only (for better layer caching)
COPY requirements-base.txt requirements-api.txt ./

# Install Python dependencies (this layer will be cached unless requirements change)
# Force pip to install CPU-only versions of PyTorch and its dependencies
# by adding the PyTorch CPU-only index. This drastically reduces image size.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-api.txt

# --- Stage 2: Final Image ---
# This stage creates the final, smaller runtime image by copying
# only the necessary artifacts from the builder stage.
FROM python:3.11-slim

WORKDIR /app

# Install minimal runtime dependencies for API only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the Python packages and essential binaries from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# Only copy essential Python binaries, not build tools
  COPY --from=builder /usr/local/bin/python* /usr/local/bin/
  COPY --from=builder /usr/local/bin/pip* /usr/local/bin/
  COPY --from=builder /usr/local/bin/uvicorn* /usr/local/bin/

# Copy Indic NLP resources from the local directory into the image
COPY indic_nlp_resources /app/indic_nlp_resources
COPY backend/ ./backend/
COPY configs/ ./configs/
COPY utils/ ./utils/

# Copy and set up entrypoint script
COPY docker/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Note: ONNX models should be mounted at runtime, not baked into the image
COPY models/bge-reranker-base-onnx /app/models/bge-reranker-base-onnx

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
