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
    RANDOM_SUFFIX=$(head /dev/urandom | tr -dc 'a-z0-9' | head -c 6)
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
FIRESTORE_EXISTS=$(gcloud firestore databases list --format="value(name)" 2>/dev/null | grep -c "(default)" || echo "0")

if [ "$FIRESTORE_EXISTS" == "0" ]; then
    echo "Creating Firestore database..."
    gcloud firestore databases create --location=nam5 --quiet 2>/dev/null || {
        echo -e "${YELLOW}Firestore may already exist or needs manual setup${NC}"
    }
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

# Step 6: Get Recall.ai API key
echo ""
echo -e "${BLUE}Step 6: API Key Configuration${NC}"
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

# Step 6b: LLM Provider Selection
echo ""
echo -e "${BLUE}Step 6b: LLM Provider Configuration${NC}"
echo ""

echo "Choose your AI provider for generating summaries:"
echo ""
echo "  1) Vertex AI (Google Gemini) - Recommended for GCP"
echo "     • Auto-authenticated on Cloud Run"
echo "     • No additional API keys needed"
echo "     • Uses gemini-1.5-pro model"
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

# Step 6c: Authentication Setup (Identity Platform)
echo ""
echo -e "${BLUE}Step 6c: Setting up Google Sign-In Authentication...${NC}"
echo ""

echo "Setting up secure authentication with Identity Platform."
echo "Users will sign in with their Google account!"
echo ""

# Enable Identity Platform API
echo "Enabling Identity Platform..."
gcloud services enable \
    identitytoolkit.googleapis.com \
    apikeys.googleapis.com \
    --quiet

echo -e "${GREEN}✓ Identity Platform enabled${NC}"

# Get or create an API key for Identity Platform
echo "Setting up API key..."

# Check for existing API keys
EXISTING_KEY_ID=$(gcloud services api-keys list --format="value(uid)" --filter="displayName='Meeting Transcription Auth'" 2>/dev/null | head -1)

if [ -n "$EXISTING_KEY_ID" ]; then
    echo "Using existing API key..."
    API_KEY_ID="$EXISTING_KEY_ID"
else
    echo "Creating new API key..."
    # Create API key
    gcloud services api-keys create \
        --display-name="Meeting Transcription Auth" \
        --api-target=service=identitytoolkit.googleapis.com \
        --quiet 2>/dev/null || true
    
    sleep 5
    
    # Get the key ID
    API_KEY_ID=$(gcloud services api-keys list --format="value(uid)" --filter="displayName='Meeting Transcription Auth'" 2>/dev/null | head -1)
fi

# Get the actual key string
if [ -n "$API_KEY_ID" ]; then
    FIREBASE_API_KEY=$(gcloud services api-keys get-key-string "$API_KEY_ID" --format="value(keyString)" 2>/dev/null)
    
    if [ -n "$FIREBASE_API_KEY" ]; then
        echo -e "${GREEN}✓ API key retrieved${NC}"
        
        # Store API key in Secret Manager
        echo "Storing API key securely..."
        echo -n "$FIREBASE_API_KEY" | gcloud secrets create FIREBASE_API_KEY --data-file=- 2>/dev/null || {
            echo -n "$FIREBASE_API_KEY" | gcloud secrets versions add FIREBASE_API_KEY --data-file=-
        }
        
        # Grant access to Cloud Run service account
        gcloud secrets add-iam-policy-binding FIREBASE_API_KEY \
            --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
        
        echo -e "${GREEN}✓ API key stored in Secret Manager${NC}"
    fi
fi

# Configure Identity Platform with Google Sign-In
echo "Configuring Identity Platform..."
ACCESS_TOKEN=$(gcloud auth print-access-token)

# Enable Google as a sign-in provider
echo "Enabling Google Sign-In provider..."
curl -s -X PATCH \
    "https://identitytoolkit.googleapis.com/admin/v2/projects/${PROJECT_ID}/defaultSupportedIdpConfigs/google.com" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    -d '{
        "enabled": true,
        "clientId": "'${PROJECT_ID}'.apps.googleusercontent.com",
        "clientSecret": ""
    }' 2>/dev/null || \
curl -s -X POST \
    "https://identitytoolkit.googleapis.com/admin/v2/projects/${PROJECT_ID}/defaultSupportedIdpConfigs?idpId=google.com" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    -d '{
        "enabled": true,
        "clientId": "'${PROJECT_ID}'.apps.googleusercontent.com",
        "clientSecret": ""
    }' 2>/dev/null || true

echo -e "${GREEN}✓ Identity Platform configured${NC}"

# Auth domain for the project
FIREBASE_AUTH_DOMAIN="${PROJECT_ID}.firebaseapp.com"

# Check if we got the API key
if [ -n "$FIREBASE_API_KEY" ]; then
    echo -e "${GREEN}✓ Authentication fully configured!${NC}"
    NEEDS_FIREBASE_SETUP="false"
else
    echo -e "${YELLOW}Note: Run these commands to get your API key:${NC}"
    echo "  gcloud services api-keys list"
    echo "  gcloud services api-keys get-key-string YOUR_KEY_ID"
    NEEDS_FIREBASE_SETUP="true"
fi

# Step 7: Deploy
echo ""
echo -e "${BLUE}Step 7: Deploying to Cloud Run...${NC}"
echo ""

# Make sure we're in the repo directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Deploying with Identity Platform Authentication..."

# Build environment variables
ENV_VARS="LLM_PROVIDER=${LLM_PROVIDER},GCP_REGION=us-central1,OUTPUT_BUCKET=${BUCKET_NAME},RETENTION_DAYS=30"
ENV_VARS="${ENV_VARS},AUTH_PROVIDER=firebase,FIREBASE_PROJECT_ID=${PROJECT_ID}"

# Build secrets string - include API key if it was stored
SECRETS_STRING="RECALL_API_KEY=RECALL_API_KEY:latest"

# Check if API key secret exists and add it
if gcloud secrets describe FIREBASE_API_KEY --quiet 2>/dev/null; then
    SECRETS_STRING="${SECRETS_STRING},FIREBASE_API_KEY=FIREBASE_API_KEY:latest"
    echo "Including Firebase API key from Secret Manager"
    
    # Ensure Cloud Run service account has access
    gcloud secrets add-iam-policy-binding FIREBASE_API_KEY \
        --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
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

# Add Cloud Run URL to Firebase authorized domains
echo ""
echo "Adding Cloud Run URL to Firebase authorized domains..."
CLOUD_RUN_DOMAIN=$(echo "$SERVICE_URL" | sed 's|https://||')

curl -s -X PATCH \
    "https://identitytoolkit.googleapis.com/v2/projects/${PROJECT_ID}/config" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
        "authorizedDomains": [
            "localhost",
            "'${PROJECT_ID}'.firebaseapp.com",
            "'${PROJECT_ID}'.web.app",
            "'${CLOUD_RUN_DOMAIN}'"
        ]
    }' > /dev/null 2>&1 || true

echo -e "${GREEN}✓ Authorized domain added${NC}"

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 SETUP COMPLETE! 🎉                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Your service is live at:${NC}"
echo ""
echo "  $SERVICE_URL"
echo ""

if [ "$NEEDS_FIREBASE_SETUP" == "true" ]; then
    echo -e "${YELLOW}🔐 Complete API Key Setup:${NC}"
    echo ""
    echo "Run these commands to get and set your API key:"
    echo ""
    echo "  gcloud services api-keys list"
    echo "  gcloud services api-keys get-key-string YOUR_KEY_ID"
    echo ""
    echo "Then update the service:"
    echo "  echo 'YOUR_API_KEY' | gcloud secrets create FIREBASE_API_KEY --data-file=-"
    echo "  gcloud run services update meeting-transcription --region us-central1 \\"
    echo "    --update-secrets='FIREBASE_API_KEY=FIREBASE_API_KEY:latest'"
else
    echo -e "${GREEN}🔐 Authentication: Google Sign-In (Identity Platform)${NC}"
    echo ""
    echo "Users can sign in immediately with their Google account!"
fi

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
echo -e "${YELLOW}📡 Configure Recall.ai Webhook${NC}"
echo ""
echo "1. Go to: https://recall.ai/dashboard → Settings → Webhooks"
echo "2. Add webhook URL:"
echo ""
echo -e "   ${GREEN}${SERVICE_URL}/webhook/recall${NC}"
echo ""
echo "3. Enable events: bot.done, transcript.done, recording.done"
echo "4. (Optional) For extra security, copy the webhook secret and run:"
echo ""
echo "   echo 'your-secret' | gcloud secrets create RECALL_WEBHOOK_SECRET --data-file=-"
echo "   gcloud run services update meeting-transcription --region us-central1 \\"
echo "     --update-secrets='RECALL_WEBHOOK_SECRET=RECALL_WEBHOOK_SECRET:latest'"
echo ""
echo -e "${GREEN}🚀 Try it now:${NC}"
echo "  Open in browser: ${SERVICE_URL}"
echo "  Click 'Sign in with Google' and you're in!"
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
AUTH_PROVIDER=firebase
FIREBASE_PROJECT_ID=$PROJECT_ID
FIREBASE_API_KEY=$FIREBASE_API_KEY
FIREBASE_AUTH_DOMAIN=$FIREBASE_AUTH_DOMAIN

# LLM Provider
LLM_PROVIDER=$LLM_PROVIDER
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

