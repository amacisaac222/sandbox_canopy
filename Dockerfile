FROM python:3.12-slim

# Install curl for health checks (force cache bust)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* && echo "Cache bust: $(date)"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY canopyiq_site/requirements.txt .

# Install dependencies  
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set working directory to canopyiq_site for the app
WORKDIR /app/canopyiq_site

# Default port (Cloud Run will set this via environment variable)
ENV PORT=8080

# Run the minimal CanopyIQ application that starts quickly
CMD sh -c "python -m uvicorn app_minimal:app --host 0.0.0.0 --port ${PORT:-8080}"