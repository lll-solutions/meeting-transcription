#!/bin/bash
#
# Meeting Transcription - Setup Script
# Run this in Google Cloud Shell to set up your project
#

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       Meeting Transcription - Setup Wizard                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Check for billing accounts
echo -e "${BLUE}Step 1: Checking billing accounts...${NC}"
echo ""

BILLING_ACCOUNTS=$(gcloud billing accounts list --format="value(name)" 2>/dev/null || echo "")

if [ -z "$BILLING_ACCOUNTS" ]; then
    echo -e "${YELLOW}⚠️  No billing accounts found.${NC}"
    echo ""
    echo "You need a billing account to use Google Cloud services."
    echo "Don't worry - new accounts get \$300 in free credits!"
    echo ""
    echo -e "${GREEN}→ Create a billing account here:${NC}"
    echo "  https://console.cloud.google.com/billing/create"
    echo ""
    read -p "Press Enter after you've created a billing account..."
    echo ""
    # Re-check
    BILLING_ACCOUNTS=$(gcloud billing accounts list --format="value(name)" 2>/dev/null || echo "")
    if [ -z "$BILLING_ACCOUNTS" ]; then
        echo -e "${RED}Still no billing accounts found. Please create one and try again.${NC}"
        exit 1
    fi
fi

# Select billing account if multiple
BILLING_COUNT=$(echo "$BILLING_ACCOUNTS" | wc -l)
if [ "$BILLING_COUNT" -gt 1 ]; then
    echo "Found multiple billing accounts:"
    gcloud billing accounts list
    echo ""
    read -p "Enter the Billing Account ID to use: " BILLING_ACCOUNT
else
    BILLING_ACCOUNT=$(echo "$BILLING_ACCOUNTS" | head -1)
    echo -e "${GREEN}✓ Using billing account: $BILLING_ACCOUNT${NC}"
fi

# Step 2: Create or select project
echo ""
echo -e "${BLUE}Step 2: Project setup...${NC}"
echo ""

echo "Would you like to:"
echo "  1) Create a NEW project for Meeting Transcription"
echo "  2) Use an EXISTING project"
echo ""
read -p "Choice (1 or 2): " PROJECT_CHOICE

if [ "$PROJECT_CHOICE" == "1" ]; then
    # Generate a unique project ID (project IDs are globally unique!)
    RANDOM_SUFFIX=$(LC_ALL=C head /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | head -c 6)
    SUGGESTED_ID="mtg-transcribe-${RANDOM_SUFFIX}"
    
    echo ""
    echo -e "${YELLOW}Note: Project IDs must be globally unique across all of Google Cloud.${NC}"
    echo ""
    read -p "Enter project ID (or press Enter for '$SUGGESTED_ID'): " PROJECT_ID
    PROJECT_ID=${PROJECT_ID:-$SUGGESTED_ID}
    
    echo ""
    echo "Creating project: $PROJECT_ID"
    
    if gcloud projects create "$PROJECT_ID" --name="Meeting Transcription" 2>&1; then
        echo -e "${GREEN}✓ Project created successfully${NC}"
    else
        echo ""
        echo -e "${RED}Failed to create project '$PROJECT_ID'.${NC}"
        echo "This could mean:"
        echo "  - The project ID is already taken (try a different name)"
        echo "  - You've hit your project quota"
        echo ""
        echo "Options:"
        echo "  1) Try a different project name"
        echo "  2) Use an existing project"
        echo ""
        read -p "Enter 1 or 2: " RETRY_CHOICE
        
        if [ "$RETRY_CHOICE" == "1" ]; then
            read -p "Enter a new project ID: " PROJECT_ID
            gcloud projects create "$PROJECT_ID" --name="Meeting Transcription" || {
                echo -e "${RED}Failed again. Please create a project manually in the console.${NC}"
                exit 1
            }
        else
            echo ""
            echo "Your existing projects:"
            gcloud projects list
            echo ""
            read -p "Enter the Project ID to use: " PROJECT_ID
        fi
    fi
    
    # Link billing
    echo ""
    echo "Linking billing account to project..."
    if gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT" 2>&1; then
        echo -e "${GREEN}✓ Billing linked successfully${NC}"
    else
        echo ""
        echo -e "${RED}Failed to link billing.${NC}"
        echo "This might mean you don't have billing admin permissions."
        echo ""
        echo "Please link billing manually:"
        echo "  https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT_ID}"
        echo ""
        read -p "Press Enter after you've linked billing..."
    fi
    
else
    echo ""
    echo "Your existing projects:"
    gcloud projects list
    echo ""
    read -p "Enter the Project ID to use: " PROJECT_ID
fi

# Set the project
echo ""
echo "Setting active project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Step 3: Enable APIs
echo ""
echo -e "${BLUE}Step 3: Enabling required APIs...${NC}"
echo ""

gcloud services enable \
    run.googleapis.com \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudresourcemanager.googleapis.com \
    serviceusage.googleapis.com \
    --quiet

echo -e "${GREEN}✓ APIs enabled${NC}"

# Step 3b: Grant Cloud Build permissions (required for Cloud Run source deploys)
echo ""
echo -e "${BLUE}Step 3b: Setting up Cloud Build permissions...${NC}"
echo ""

# Get project number
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

# Grant Cloud Build service account the necessary roles
echo "Granting Cloud Build service account permissions..."

# The default compute service account needs these roles
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectViewer" \
    --quiet 2>/dev/null || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/logging.logWriter" \
    --quiet 2>/dev/null || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/artifactregistry.writer" \
    --quiet 2>/dev/null || true

# Cloud Build service account also needs permissions
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/run.admin" \
    --quiet 2>/dev/null || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser" \
    --quiet 2>/dev/null || true

echo -e "${GREEN}✓ Cloud Build permissions configured${NC}"

# Wait a moment for IAM propagation
echo "Waiting for IAM changes to propagate..."
sleep 10

# Step 4: Create Firestore database (if needed)
echo ""
echo -e "${BLUE}Step 4: Setting up Firestore...${NC}"
echo ""

# Check if Firestore exists
FIRESTORE_EXISTS=$(gcloud firestore databases list --format="value(name)" 2>/dev/null | grep -c "(default)" || true)

if [ "$FIRESTORE_EXISTS" == "0" ]; then
    echo "Creating Firestore database..."
    if gcloud firestore databases create --location=nam5 --type=firestore-native --quiet 2>&1; then
        echo -e "${GREEN}✓ Firestore database created${NC}"
        echo "Waiting for Firestore to be ready..."
        sleep 10
    else
        echo -e "${RED}❌ Firestore creation failed!${NC}"
        echo ""
        echo "Please create Firestore manually:"
        echo "  1. Visit: https://console.cloud.google.com/firestore?project=${PROJECT_ID}"
        echo "  2. Choose 'Native Mode'"
        echo "  3. Select location: nam5 (United States)"
        echo "  4. Click 'Create Database'"
        echo ""
        read -p "Press Enter after you've created the Firestore database..."
    fi

    # Verify Firestore is now available
    echo "Verifying Firestore..."
    RETRY_COUNT=0
    MAX_RETRIES=12
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        FIRESTORE_EXISTS=$(gcloud firestore databases list --format="value(name)" 2>/dev/null | grep -c "(default)" || echo "0")
        if [ "$FIRESTORE_EXISTS" != "0" ]; then
            echo -e "${GREEN}✓ Firestore is ready!${NC}"
            break
        fi
        echo "Still waiting for Firestore... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 5
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done

    if [ "$FIRESTORE_EXISTS" == "0" ]; then
        echo -e "${RED}❌ Firestore is still not available. Cannot continue.${NC}"
        echo "Please check the Firestore console and try again."
        exit 1
    fi
else
    echo -e "${GREEN}✓ Firestore already configured${NC}"
fi

# Step 5: Create storage bucket
echo ""
echo -e "${BLUE}Step 5: Creating storage bucket...${NC}"
echo ""

BUCKET_NAME="${PROJECT_ID}-meeting-outputs"
gsutil mb -l us-central1 "gs://${BUCKET_NAME}" 2>/dev/null || {
    echo -e "${GREEN}✓ Bucket already exists${NC}"
}
echo -e "${GREEN}✓ Storage bucket: ${BUCKET_NAME}${NC}"

# Step 6: Feature Configuration
echo ""
echo -e "${BLUE}Step 6: Feature Configuration${NC}"
echo ""

echo "Configure features for your deployment:"
echo ""
echo "Bot Joining Feature:"
echo "  • Allows bots to automatically join live meetings (Zoom, Google Meet, etc.)"
echo "  • If disabled, users can only upload pre-recorded transcripts"
echo "  • Useful for HIPAA-compliant deployments (disable bot joining for privacy)"
echo ""
read -p "Enable bot joining feature? [Y/n]: " BOT_JOINING_CHOICE
BOT_JOINING_CHOICE=${BOT_JOINING_CHOICE:-Y}

if [[ "$BOT_JOINING_CHOICE" =~ ^[Yy]$ ]]; then
    FEATURES_BOT_JOINING="true"
    echo -e "${GREEN}✓ Bot joining: ENABLED${NC}"
else
    FEATURES_BOT_JOINING="false"
    echo -e "${YELLOW}⚠️  Bot joining: DISABLED (upload-only mode)${NC}"
fi

# Step 6a: Get Recall.ai API key (only if bot joining enabled)
if [[ "$FEATURES_BOT_JOINING" == "true" ]]; then
    echo ""
    echo -e "${BLUE}Step 6a: Recall.ai API Key${NC}"
    echo ""

    echo "You need a Recall.ai API key for the meeting bot."
    echo ""
    echo -e "${GREEN}→ Get your API key from: https://recall.ai${NC}"
    echo ""
    read -sp "Paste your Recall.ai API Key (hidden): " RECALL_KEY
    echo ""

    # Store in Secret Manager
    echo "Storing API key in Secret Manager..."
    echo -n "$RECALL_KEY" | gcloud secrets create RECALL_API_KEY --data-file=- 2>/dev/null || {
        echo -n "$RECALL_KEY" | gcloud secrets versions add RECALL_API_KEY --data-file=-
    }

    # Grant Cloud Run service account access to the secret
    echo "Granting secret access to Cloud Run service account..."
    gcloud secrets add-iam-policy-binding RECALL_API_KEY \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true

    echo -e "${GREEN}✓ Recall.ai API key stored securely${NC}"

    # Step 6a2: Get Recall.ai Webhook Secret
    echo ""
    echo "You also need your Recall.ai Webhook Secret for secure webhook verification."
    echo ""
    echo -e "${GREEN}→ Find it at: https://recall.ai/dashboard → Settings → Webhooks${NC}"
    echo ""
    read -sp "Paste your Recall.ai Webhook Secret (hidden, starts with whsec_): " RECALL_WEBHOOK_SECRET
    echo ""

    if [ -n "$RECALL_WEBHOOK_SECRET" ]; then
        # Store in Secret Manager
        echo "Storing Webhook Secret in Secret Manager..."
        echo -n "$RECALL_WEBHOOK_SECRET" | gcloud secrets create RECALL_WEBHOOK_SECRET --data-file=- 2>/dev/null || {
            echo -n "$RECALL_WEBHOOK_SECRET" | gcloud secrets versions add RECALL_WEBHOOK_SECRET --data-file=-
        }

        # Grant Cloud Run service account access to the secret
        gcloud secrets add-iam-policy-binding RECALL_WEBHOOK_SECRET \
            --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true

        echo -e "${GREEN}✓ Recall.ai Webhook Secret stored securely${NC}"
    else
        echo -e "${YELLOW}⚠️  No Webhook Secret provided - webhooks will not be verified${NC}"
        echo -e "${YELLOW}   You can add it later with the commands shown at the end${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}⚠️  Skipping Recall.ai API key (bot joining disabled)${NC}"
fi

# Step 6b: LLM Provider Selection
echo ""
echo -e "${BLUE}Step 6b: LLM Provider Configuration${NC}"
echo ""

echo "Choose your AI provider for generating summaries:"
echo ""
echo "  1) Vertex AI (Google Gemini) - Recommended for GCP"
echo "     • Auto-authenticated on Cloud Run"
echo "     • No additional API keys needed"
echo "     • Uses gemini-3-pro-preview model"
echo ""
echo "  2) Azure OpenAI (GPT-4)"
echo "     • Requires Azure OpenAI resource"
echo "     • Uses gpt-4o model"
echo "     • Great if you have existing Azure investment"
echo ""
read -p "Choice [1]: " LLM_CHOICE
LLM_CHOICE=${LLM_CHOICE:-1}

if [ "$LLM_CHOICE" = "2" ]; then
    LLM_PROVIDER="azure_openai"
    echo ""
    echo -e "${YELLOW}Setting up Azure OpenAI...${NC}"
    echo ""
    echo "You'll need your Azure OpenAI credentials."
    echo "Find them in Azure Portal → Your OpenAI Resource → Keys and Endpoint"
    echo ""
    
    read -sp "Enter your Azure OpenAI API Key (hidden): " AZURE_KEY
    echo ""
    read -p "Enter your Azure OpenAI Endpoint (e.g., https://your-resource.openai.azure.com/): " AZURE_ENDPOINT
    read -p "Enter your Azure OpenAI Deployment name [gpt-4o]: " AZURE_DEPLOYMENT
    AZURE_DEPLOYMENT=${AZURE_DEPLOYMENT:-gpt-4o}
    
    echo ""
    echo "Storing Azure credentials in Secret Manager..."
    
    # Create Azure secrets
    echo -n "$AZURE_KEY" | gcloud secrets create AZURE_OPENAI_API_KEY --data-file=- 2>/dev/null || {
        echo -n "$AZURE_KEY" | gcloud secrets versions add AZURE_OPENAI_API_KEY --data-file=-
    }
    echo -n "$AZURE_ENDPOINT" | gcloud secrets create AZURE_OPENAI_ENDPOINT --data-file=- 2>/dev/null || {
        echo -n "$AZURE_ENDPOINT" | gcloud secrets versions add AZURE_OPENAI_ENDPOINT --data-file=-
    }
    echo -n "$AZURE_DEPLOYMENT" | gcloud secrets create AZURE_OPENAI_DEPLOYMENT --data-file=- 2>/dev/null || {
        echo -n "$AZURE_DEPLOYMENT" | gcloud secrets versions add AZURE_OPENAI_DEPLOYMENT --data-file=-
    }
    
    # Grant access to Cloud Run service account
    for SECRET in AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_DEPLOYMENT; do
        gcloud secrets add-iam-policy-binding $SECRET \
            --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
    done
    
    echo -e "${GREEN}✓ Azure OpenAI credentials stored securely${NC}"
else
    LLM_PROVIDER="vertex_ai"
    echo -e "${GREEN}✓ Using Vertex AI (Gemini) - auto-authenticated on GCP${NC}"
fi

# Step 6c: Admin User Setup
echo ""
echo -e "${BLUE}Step 6c: Admin User Configuration${NC}"
echo ""

echo "We'll create an initial Admin user for your application."
echo ""

read -p "Enter Admin Email [admin@example.com]: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.com}

read -p "Enter Admin Full Name [Admin User]: " ADMIN_NAME
ADMIN_NAME=${ADMIN_NAME:-Admin User}

echo ""
echo "Enter a password for the admin user."
echo "Leave empty to generate a secure random password."
read -sp "Password: " ADMIN_PASSWORD
echo ""

if [ -z "$ADMIN_PASSWORD" ]; then
    # Generate secure password
    ADMIN_PASSWORD=$(openssl rand -base64 12)
    echo -e "Generated password: ${GREEN}$ADMIN_PASSWORD${NC}"
fi

# Generate JWT Secret
echo ""
echo "Generating JWT Secret..."
JWT_SECRET=$(openssl rand -hex 32)

# Store JWT Secret in Secret Manager
echo "Storing JWT Secret in Secret Manager..."
echo -n "$JWT_SECRET" | gcloud secrets create JWT_SECRET --data-file=- 2>/dev/null || {
    echo -n "$JWT_SECRET" | gcloud secrets versions add JWT_SECRET --data-file=-
}

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding JWT_SECRET \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet 2>/dev/null || true

# Generate Setup API Key (for securing the /api/auth/setup endpoint)
echo ""
echo "Generating Setup API Key..."
SETUP_API_KEY=$(openssl rand -hex 32)

# Store Setup API Key in Secret Manager
echo "Storing Setup API Key in Secret Manager..."
echo -n "$SETUP_API_KEY" | gcloud secrets create SETUP_API_KEY --data-file=- 2>/dev/null || {
    echo -n "$SETUP_API_KEY" | gcloud secrets versions add SETUP_API_KEY --data-file=-
}

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding SETUP_API_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet 2>/dev/null || true

echo -e "${GREEN}✓ Admin configuration ready${NC}"

# Step 7: Deploy
echo ""
echo -e "${BLUE}Step 7: Deploying to Cloud Run...${NC}"
echo ""

# Make sure we're in the repo directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Deploying with Identity Platform Authentication..."

# Build environment variables (SERVICE_URL and WEBHOOK_URL will be set after deployment)
ENV_VARS="LLM_PROVIDER=${LLM_PROVIDER},GCP_REGION=us-central1,OUTPUT_BUCKET=${BUCKET_NAME},RETENTION_DAYS=30"
ENV_VARS="${ENV_VARS},AUTH_PROVIDER=db,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GCP_PROJECT_NUMBER=${PROJECT_NUMBER}"
ENV_VARS="${ENV_VARS},FEATURES_BOT_JOINING=${FEATURES_BOT_JOINING}"

# Build secrets string (always include JWT_SECRET and SETUP_API_KEY)
SECRETS_STRING="JWT_SECRET=JWT_SECRET:latest,SETUP_API_KEY=SETUP_API_KEY:latest"

# Add Recall API key and webhook secret if bot joining is enabled
if [ "$FEATURES_BOT_JOINING" = "true" ]; then
    echo "Including Recall.ai API key from Secret Manager"
    SECRETS_STRING="${SECRETS_STRING},RECALL_API_KEY=RECALL_API_KEY:latest"

    # Check if webhook secret exists in Secret Manager
    WEBHOOK_SECRET_EXISTS=$(gcloud secrets describe RECALL_WEBHOOK_SECRET --format="value(name)" 2>/dev/null || echo "")
    if [ -n "$WEBHOOK_SECRET_EXISTS" ]; then
        echo "Including Recall.ai Webhook Secret from Secret Manager"
        SECRETS_STRING="${SECRETS_STRING},RECALL_WEBHOOK_SECRET=RECALL_WEBHOOK_SECRET:latest"
    else
        echo -e "${YELLOW}⚠️  Webhook secret not found - webhooks will not be verified${NC}"
    fi
fi

# Add Azure OpenAI secrets if using Azure
if [ "$LLM_PROVIDER" = "azure_openai" ]; then
    echo "Including Azure OpenAI secrets from Secret Manager"
    SECRETS_STRING="${SECRETS_STRING},AZURE_OPENAI_API_KEY=AZURE_OPENAI_API_KEY:latest"
    SECRETS_STRING="${SECRETS_STRING},AZURE_OPENAI_ENDPOINT=AZURE_OPENAI_ENDPOINT:latest"
    SECRETS_STRING="${SECRETS_STRING},AZURE_OPENAI_DEPLOYMENT=AZURE_OPENAI_DEPLOYMENT:latest"
fi

gcloud run deploy meeting-transcription \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets="${SECRETS_STRING}" \
    --set-env-vars="${ENV_VARS}" \
    --memory 1Gi \
    --timeout 600 \
    --quiet

# Get service URL
SERVICE_URL=$(gcloud run services describe meeting-transcription --region us-central1 --format="value(status.url)")

# Update service with SERVICE_URL and WEBHOOK_URL now that we know the actual URL
echo "Updating service with correct URLs..."
gcloud run services update meeting-transcription \
    --region us-central1 \
    --update-env-vars="SERVICE_URL=${SERVICE_URL},WEBHOOK_URL=${SERVICE_URL}/webhook/recall" \
    --quiet

echo -e "${GREEN}✓ Service URLs configured${NC}"

# Create Admin User via API
echo ""
echo "Creating Admin User via API..."
echo "  Email: $ADMIN_EMAIL"

# Use the /api/auth/setup endpoint with setup API key for security
SETUP_RESPONSE=$(curl -s -X POST "${SERVICE_URL}/api/auth/setup" \
    -H "Content-Type: application/json" \
    -H "X-Setup-Key: ${SETUP_API_KEY}" \
    -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"name\":\"${ADMIN_NAME}\"}" \
    -w "\n%{http_code}")

HTTP_CODE=$(echo "$SETUP_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$SETUP_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✓ Admin user created successfully${NC}"
elif [ "$HTTP_CODE" == "403" ]; then
    echo -e "${YELLOW}⚠️  Admin user already exists (setup previously completed)${NC}"
else
    echo -e "${YELLOW}⚠️  Failed to create admin user (HTTP $HTTP_CODE)${NC}"
    echo "Response: $RESPONSE_BODY"
    echo ""
    echo "You can create the admin user manually by running:"
    echo "  curl -X POST ${SERVICE_URL}/api/auth/setup \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -H 'X-Setup-Key: ${SETUP_API_KEY}' \\"
    echo "    -d '{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"name\":\"${ADMIN_NAME}\"}'"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 SETUP COMPLETE! 🎉                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Your service is live at:${NC}"
echo ""
echo "  $SERVICE_URL"
echo ""

echo -e "${GREEN}🔐 Login Credentials:${NC}"
echo "  Email:    $ADMIN_EMAIL"
echo "  Password: $ADMIN_PASSWORD"
echo ""
echo "  (Save these credentials!)"

# Show LLM provider info
echo ""
if [ "$LLM_PROVIDER" = "azure_openai" ]; then
    echo -e "${GREEN}🤖 AI Provider: Azure OpenAI (GPT-4)${NC}"
    echo "   Endpoint: $AZURE_ENDPOINT"
    echo "   Deployment: $AZURE_DEPLOYMENT"
else
    echo -e "${GREEN}🤖 AI Provider: Vertex AI (Google Gemini)${NC}"
    echo "   Auto-authenticated on Cloud Run"
fi
echo ""

# =============================================================================
# Setup Cloud Tasks for background processing
# =============================================================================
echo -e "${BLUE}Setting up Cloud Tasks for background processing...${NC}"
echo ""

# Enable Cloud Tasks API
echo "Enabling Cloud Tasks API..."
gcloud services enable cloudtasks.googleapis.com --quiet

# Wait for API to be fully enabled
echo "Waiting for Cloud Tasks API to be ready..."
sleep 10

# Check if API is ready by trying to list queues (with retry logic)
MAX_ATTEMPTS=6  # Try for up to 60 seconds total
ATTEMPT=0
API_READY=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if gcloud tasks queues list --location=us-central1 --limit=1 >/dev/null 2>&1; then
        API_READY=true
        echo -e "${GREEN}✓ Cloud Tasks API is ready${NC}"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
        echo "API not ready yet, waiting... (attempt $ATTEMPT/$MAX_ATTEMPTS)"
        sleep 10
    fi
done

if [ "$API_READY" = false ]; then
    echo -e "${YELLOW}⚠️  Cloud Tasks API may not be fully ready yet${NC}"
    echo "Proceeding anyway - queue creation might fail but can be done manually"
fi

# Create task queue
QUEUE_NAME="transcript-processing"
QUEUE_EXISTS=$(gcloud tasks queues describe $QUEUE_NAME --location us-central1 --format="value(name)" 2>/dev/null || echo "")

if [ -z "$QUEUE_EXISTS" ]; then
    echo "Creating Cloud Tasks queue..."
    if gcloud tasks queues create $QUEUE_NAME --location=us-central1 --quiet; then
        echo -e "${GREEN}✓ Cloud Tasks queue created${NC}"
    else
        echo -e "${RED}❌ Failed to create Cloud Tasks queue${NC}"
        echo "This might mean the Cloud Tasks API needs more time to enable."
        echo "You can create it manually later with:"
        echo "  gcloud tasks queues create transcript-processing --location=us-central1"
    fi
else
    echo -e "${GREEN}✓ Cloud Tasks queue already exists${NC}"
fi

# Grant service account permission to create tasks
echo "Granting cloudtasks.enqueuer permission..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/cloudtasks.enqueuer" \
    --quiet

# Grant service account permission to invoke Cloud Run (for tasks to call the service)
echo "Granting run.invoker permission..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --quiet

echo -e "${GREEN}✓ Cloud Tasks configured${NC}"
echo ""

# =============================================================================
# Setup Firestore Indexes for Scheduled Meetings
# =============================================================================
echo -e "${BLUE}Setting up Firestore indexes for scheduled meetings...${NC}"
echo ""

# Deploy indexes in background (this can take 5-15 minutes)
echo "Creating Firestore composite indexes (this runs in the background)..."

# Create all required indexes for scheduled meetings
# Index 1: For Cloud Scheduler execution (status + scheduled_time)
gcloud firestore indexes composite create \
    --collection-group=scheduled_meetings \
    --query-scope=COLLECTION \
    --field-config=field-path=status,order=ascending \
    --field-config=field-path=scheduled_time,order=ascending \
    --quiet 2>&1 &

# Index 2: For listing user's scheduled meetings (user + scheduled_time)
gcloud firestore indexes composite create \
    --collection-group=scheduled_meetings \
    --query-scope=COLLECTION \
    --field-config=field-path=user,order=ascending \
    --field-config=field-path=scheduled_time,order=descending \
    --quiet 2>&1 &

# Index 3: For filtering by user and status (user + status + scheduled_time)
gcloud firestore indexes composite create \
    --collection-group=scheduled_meetings \
    --query-scope=COLLECTION \
    --field-config=field-path=user,order=ascending \
    --field-config=field-path=status,order=ascending \
    --field-config=field-path=scheduled_time,order=descending \
    --quiet 2>&1 &

echo -e "${YELLOW}⏱️  Note: Firestore indexes are building in the background.${NC}"
echo -e "${YELLOW}   The scheduled meetings feature will be fully available in 5-15 minutes.${NC}"
echo -e "${YELLOW}   All other features are available immediately.${NC}"
echo ""
echo "   To check index status:"
echo "   gcloud firestore indexes composite list"
echo ""

echo -e "${YELLOW}📡 Configure Recall.ai Webhook${NC}"
echo ""
echo "1. Go to: https://recall.ai/dashboard → Settings → Webhooks"
echo "2. Verify webhook URL is set to:"
echo ""
echo -e "   ${GREEN}${SERVICE_URL}/webhook/recall${NC}"
echo ""
echo "3. Ensure these events are enabled: bot.done, transcript.done, recording.done"
echo ""
if [ "$FEATURES_BOT_JOINING" = "true" ] && [ -z "$WEBHOOK_SECRET_EXISTS" ]; then
    echo -e "${YELLOW}⚠️  Note: Webhook secret was not provided during setup.${NC}"
    echo "   To add it later for enhanced security:"
    echo ""
    echo "   echo 'your-secret' | gcloud secrets create RECALL_WEBHOOK_SECRET --data-file=-"
    echo "   gcloud secrets add-iam-policy-binding RECALL_WEBHOOK_SECRET \\"
    echo "     --member=\"serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com\" \\"
    echo "     --role=\"roles/secretmanager.secretAccessor\""
    echo "   gcloud run services update meeting-transcription --region us-central1 \\"
    echo "     --update-secrets='RECALL_WEBHOOK_SECRET=RECALL_WEBHOOK_SECRET:latest'"
    echo ""
fi

echo -e "${GREEN}🚀 Try it now:${NC}"
echo "  Open in browser: ${SERVICE_URL}"
echo "  Sign in with your email and password!"
echo ""

# Save configuration for reference
cat > .env.deployed << EOF
# Deployed Configuration - $(date)
PROJECT_ID=$PROJECT_ID
PROJECT_NUMBER=$PROJECT_NUMBER
SERVICE_URL=$SERVICE_URL
BUCKET_NAME=$BUCKET_NAME
WEBHOOK_URL=${SERVICE_URL}/webhook/recall

# Authentication
AUTH_PROVIDER=db
ADMIN_EMAIL=$ADMIN_EMAIL

# LLM Provider
LLM_PROVIDER=$LLM_PROVIDER

# Features
FEATURES_BOT_JOINING=$FEATURES_BOT_JOINING
EOF

# Add Azure info if applicable
if [ "$LLM_PROVIDER" = "azure_openai" ]; then
    cat >> .env.deployed << EOF
AZURE_OPENAI_ENDPOINT=$AZURE_ENDPOINT
AZURE_OPENAI_DEPLOYMENT=$AZURE_DEPLOYMENT
# API Key stored in Secret Manager
EOF
fi

echo -e "${GREEN}✓ Configuration saved to .env.deployed${NC}"
echo ""
echo "Share the URL with your team - they can sign in immediately!"
echo ""

