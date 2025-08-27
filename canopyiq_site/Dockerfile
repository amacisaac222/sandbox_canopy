FROM python:3.12-slim

# Install curl for health checks and cache bust
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* && echo "Cache bust: $(date)"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set working directory
WORKDIR /app

# Cloud Run uses PORT environment variable (default 8080)
ENV PORT=8080

# Use app_production for production deployment
CMD sh -c "python -m uvicorn app_production:app --host 0.0.0.0 --port ${PORT:-8080}"