#!/bin/bash

# Cloud Run deployment script for CanopyIQ
set -e

# Configuration
PROJECT_ID="your-project-id-here"  # Replace with your GCP project ID
SERVICE_NAME="canopyiq-site"
REGION="us-central1"
IMAGE_TAG="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying CanopyIQ to Google Cloud Run"
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"

# Authenticate (if needed)
echo "🔐 Checking authentication..."
gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null || {
    echo "Please authenticate with: gcloud auth login"
    exit 1
}

# Set project
echo "⚙️ Setting project..."
gcloud config set project $PROJECT_ID

# Build and push image
echo "🔨 Building Docker image..."
gcloud builds submit --tag $IMAGE_TAG

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_TAG \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --ingress all \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 300 \
  --concurrency 80

echo "✅ Deployment complete!"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format "value(status.url)")
echo "🌐 Service URL: $SERVICE_URL"

# Test the deployment
echo "🔍 Testing deployment..."
curl -f "$SERVICE_URL/health" && echo "Health check passed!" || echo "Health check failed!"

echo "🎉 CanopyIQ is now live on Cloud Run!"
echo "Next steps:"
echo "1. Set up Cloudflare DNS to point canopyiq.ai → $SERVICE_URL"
echo "2. Add PostgreSQL database when ready for authentication"
echo "3. Configure environment variables for production features"