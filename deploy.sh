#!/bin/bash
# =============================================================================
# deploy.sh - Quick rebuild and deploy (assumes initial setup already done)
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    DEPLOY TO CLOUD RUN                         ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Get project info
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID${NC}"
    exit 1
fi

echo -e "Project: ${GREEN}$PROJECT_ID${NC}"
echo ""

# Get existing service config
SERVICE_URL=$(gcloud run services describe meeting-transcription --region us-central1 --format="value(status.url)" 2>/dev/null || echo "")

if [ -z "$SERVICE_URL" ]; then
    echo -e "${YELLOW}Service not found. Run setup.sh for initial deployment.${NC}"
    exit 1
fi

echo -e "Service URL: ${GREEN}$SERVICE_URL${NC}"
echo ""

# Build secrets string
SECRETS_STRING="RECALL_API_KEY=RECALL_API_KEY:latest"

if gcloud secrets describe FIREBASE_API_KEY --quiet 2>/dev/null; then
    SECRETS_STRING="${SECRETS_STRING},FIREBASE_API_KEY=FIREBASE_API_KEY:latest"
    
    # Ensure permissions
    gcloud secrets add-iam-policy-binding FIREBASE_API_KEY \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
fi

if gcloud secrets describe RECALL_WEBHOOK_SECRET --quiet 2>/dev/null; then
    SECRETS_STRING="${SECRETS_STRING},RECALL_WEBHOOK_SECRET=RECALL_WEBHOOK_SECRET:latest"
fi

# Get bucket name
BUCKET_NAME="${PROJECT_ID}-meeting-outputs"

# Build environment variables
ENV_VARS="LLM_PROVIDER=vertex_ai,GCP_REGION=us-central1,OUTPUT_BUCKET=${BUCKET_NAME},RETENTION_DAYS=30"
ENV_VARS="${ENV_VARS},AUTH_PROVIDER=firebase,FIREBASE_PROJECT_ID=${PROJECT_ID}"

echo -e "${BLUE}Deploying...${NC}"
echo ""

gcloud run deploy meeting-transcription \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets="${SECRETS_STRING}" \
    --set-env-vars="${ENV_VARS}" \
    --memory 1Gi \
    --timeout 600 \
    --quiet

echo ""
echo -e "${GREEN}✓ Deployed successfully!${NC}"
echo ""
echo -e "URL: ${GREEN}${SERVICE_URL}${NC}"
echo ""

