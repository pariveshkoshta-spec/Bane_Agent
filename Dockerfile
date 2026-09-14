# Use official NVIDIA PyTorch image as base (or standard Python for CPU deployment)
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for SQLite and FAISS
RUN apt-get update && apt-get install -y build-essential libsqlite3-dev

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/

# Expose API port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
