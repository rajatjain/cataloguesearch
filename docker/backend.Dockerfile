# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file from the backend directory into the container at /app
COPY backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code into the container at /app
COPY backend/ .

# Run uvicorn server. It will be accessible on port 8000 inside the container network.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]