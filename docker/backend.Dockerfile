# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Create a non-root user and group for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file from the backend directory into the container at /app
# Own the app directory before copying files
RUN chown appuser:appuser /app
COPY backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code into the container at /app
COPY backend/ .

# Ensure the application files are owned by the new user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Run uvicorn server. It will be accessible on port 8000 inside the container network.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]