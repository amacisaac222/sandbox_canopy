FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 PORT=8080

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

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

# Cloud Run uses PORT environment variable (default 8080)
CMD ["uvicorn", "app_production:app", "--host", "0.0.0.0", "--port", "8080"]