# Cloud Run deployment script for CanopyIQ (PowerShell)

# Configuration
$PROJECT_ID = "your-project-id-here"  # Replace with your GCP project ID
$SERVICE_NAME = "canopyiq-site"
$REGION = "us-central1"
$IMAGE_TAG = "gcr.io/$PROJECT_ID/$SERVICE_NAME"

Write-Host "🚀 Deploying CanopyIQ to Google Cloud Run" -ForegroundColor Green
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "Service: $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan

# Set project
Write-Host "⚙️ Setting project..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Build and push image
Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
gcloud builds submit --tag $IMAGE_TAG

# Deploy to Cloud Run
Write-Host "🚀 Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
  --image $IMAGE_TAG `
  --platform managed `
  --region $REGION `
  --allow-unauthenticated `
  --ingress all `
  --memory 512Mi `
  --cpu 1 `
  --min-instances 0 `
  --max-instances 10 `
  --timeout 300 `
  --concurrency 80

Write-Host "✅ Deployment complete!" -ForegroundColor Green

# Get the service URL
$SERVICE_URL = (gcloud run services describe $SERVICE_NAME --region $REGION --format "value(status.url)")
Write-Host "🌐 Service URL: $SERVICE_URL" -ForegroundColor Cyan

# Test the deployment
Write-Host "🔍 Testing deployment..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$SERVICE_URL/health" -UseBasicParsing
    Write-Host "Health check passed!" -ForegroundColor Green
} catch {
    Write-Host "Health check failed!" -ForegroundColor Red
}

Write-Host "🎉 CanopyIQ is now live on Cloud Run!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Set up Cloudflare DNS to point canopyiq.ai → $SERVICE_URL" -ForegroundColor White
Write-Host "2. Add PostgreSQL database when ready for authentication" -ForegroundColor White
Write-Host "3. Configure environment variables for production features" -ForegroundColor White