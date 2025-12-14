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

# =============================================================================
# LLM Provider Selection
# =============================================================================
echo -e "${BLUE}Select LLM Provider:${NC}"
echo "  1) Vertex AI (Google Gemini) - Default, auto-authenticated on GCP"
echo "  2) Azure OpenAI (GPT-4) - Requires Azure secrets"
echo ""
read -p "Choice [1]: " LLM_CHOICE
LLM_CHOICE=${LLM_CHOICE:-1}

if [ "$LLM_CHOICE" = "2" ]; then
    LLM_PROVIDER="azure_openai"
    echo -e "${YELLOW}Using Azure OpenAI${NC}"
    
    # Check if Azure secrets exist
    if ! gcloud secrets describe AZURE_OPENAI_API_KEY --quiet 2>/dev/null; then
        echo ""
        echo -e "${YELLOW}Azure OpenAI secrets not found. Let's create them.${NC}"
        echo ""
        
        read -p "Enter your Azure OpenAI API Key: " AZURE_KEY
        read -p "Enter your Azure OpenAI Endpoint (e.g., https://your-resource.openai.azure.com/): " AZURE_ENDPOINT
        read -p "Enter your Azure OpenAI Deployment name [gpt-4o]: " AZURE_DEPLOYMENT
        AZURE_DEPLOYMENT=${AZURE_DEPLOYMENT:-gpt-4o}
        
        # Create secrets
        echo -n "$AZURE_KEY" | gcloud secrets create AZURE_OPENAI_API_KEY --data-file=-
        echo -n "$AZURE_ENDPOINT" | gcloud secrets create AZURE_OPENAI_ENDPOINT --data-file=-
        echo -n "$AZURE_DEPLOYMENT" | gcloud secrets create AZURE_OPENAI_DEPLOYMENT --data-file=-
        
        echo -e "${GREEN}✓ Azure secrets created${NC}"
    fi
    
    # Grant access to compute service account
    for SECRET in AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_DEPLOYMENT; do
        gcloud secrets add-iam-policy-binding $SECRET \
            --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
    done
else
    LLM_PROVIDER="vertex_ai"
    echo -e "${GREEN}Using Vertex AI (Gemini)${NC}"
fi

echo ""

# =============================================================================
# Build secrets string
# =============================================================================
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

# Add Azure secrets if using Azure OpenAI
if [ "$LLM_PROVIDER" = "azure_openai" ]; then
    SECRETS_STRING="${SECRETS_STRING},AZURE_OPENAI_API_KEY=AZURE_OPENAI_API_KEY:latest"
    SECRETS_STRING="${SECRETS_STRING},AZURE_OPENAI_ENDPOINT=AZURE_OPENAI_ENDPOINT:latest"
    SECRETS_STRING="${SECRETS_STRING},AZURE_OPENAI_DEPLOYMENT=AZURE_OPENAI_DEPLOYMENT:latest"
fi

# Get bucket name
BUCKET_NAME="${PROJECT_ID}-meeting-outputs"

# Build environment variables
ENV_VARS="LLM_PROVIDER=${LLM_PROVIDER},GCP_REGION=us-central1,OUTPUT_BUCKET=${BUCKET_NAME},RETENTION_DAYS=30"
ENV_VARS="${ENV_VARS},AUTH_PROVIDER=db,GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
ENV_VARS="${ENV_VARS},SERVICE_URL=${SERVICE_URL},GCP_PROJECT_NUMBER=${PROJECT_NUMBER}"

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

# =============================================================================
# Setup Cloud Scheduler for scheduled meetings
# =============================================================================
echo -e "${BLUE}Setting up Cloud Scheduler for scheduled meetings...${NC}"
echo ""

SCHEDULER_JOB_NAME="meeting-scheduler"
ENDPOINT_URL="${SERVICE_URL}/api/scheduled-meetings/execute"
SCHEDULE="*/2 * * * *"  # Every 2 minutes

# Enable Cloud Scheduler API
gcloud services enable cloudscheduler.googleapis.com --quiet 2>/dev/null || true

# Check if scheduler job already exists
if gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" --location us-central1 &>/dev/null; then
    echo -e "${YELLOW}Updating existing scheduler job...${NC}"

    gcloud scheduler jobs update http "$SCHEDULER_JOB_NAME" \
        --location us-central1 \
        --schedule="$SCHEDULE" \
        --uri="$ENDPOINT_URL" \
        --http-method=POST \
        --oidc-service-account-email="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --oidc-token-audience="$ENDPOINT_URL" \
        --quiet 2>/dev/null || true

    echo -e "${GREEN}✓ Scheduler job updated${NC}"
else
    echo -e "${BLUE}Creating scheduler job...${NC}"

    gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" \
        --location us-central1 \
        --schedule="$SCHEDULE" \
        --uri="$ENDPOINT_URL" \
        --http-method=POST \
        --oidc-service-account-email="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --oidc-token-audience="$ENDPOINT_URL" \
        --quiet 2>/dev/null || true

    echo -e "${GREEN}✓ Scheduler job created${NC}"
fi

echo ""
echo -e "${GREEN}✓ Cloud Scheduler configured to check for scheduled meetings every 2 minutes${NC}"
echo ""

# =============================================================================
# Setup Cloud Tasks for background processing
# =============================================================================
echo -e "${BLUE}Setting up Cloud Tasks for background processing...${NC}"
echo ""

# Enable Cloud Tasks API
gcloud services enable cloudtasks.googleapis.com --quiet 2>/dev/null || true

# Create task queue if it doesn't exist
QUEUE_NAME="transcript-processing"
QUEUE_EXISTS=$(gcloud tasks queues describe $QUEUE_NAME --location us-central1 --format="value(name)" 2>/dev/null || echo "")

if [ -z "$QUEUE_EXISTS" ]; then
    echo "Creating Cloud Tasks queue..."
    gcloud tasks queues create $QUEUE_NAME \
        --location=us-central1 \
        --quiet 2>/dev/null || true
    echo -e "${GREEN}✓ Cloud Tasks queue created${NC}"
else
    echo -e "${GREEN}✓ Cloud Tasks queue already exists${NC}"
fi

# Grant service account permission to create tasks
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/cloudtasks.enqueuer" \
    --quiet 2>/dev/null || true

# Grant service account permission to invoke Cloud Run (for tasks to call the service)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --quiet 2>/dev/null || true

echo -e "${GREEN}✓ Cloud Tasks configured${NC}"
echo ""

