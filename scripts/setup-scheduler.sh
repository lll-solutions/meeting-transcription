#!/bin/bash
# =============================================================================
# setup-scheduler.sh - Configure Cloud Scheduler for scheduled meeting joins
# =============================================================================
#
# This script sets up a Cloud Scheduler job that triggers the scheduled
# meeting execution endpoint every 2 minutes.
#
# Prerequisites:
# - Cloud Run service must be deployed
# - Cloud Scheduler API must be enabled
#
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
echo -e "${BLUE}          CLOUD SCHEDULER SETUP - SCHEDULED MEETINGS            ${NC}"
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

# Configuration
REGION="us-central1"
SERVICE_NAME="meeting-transcription"
SCHEDULER_JOB_NAME="meeting-scheduler"
SCHEDULE="*/2 * * * *"  # Every 2 minutes

# Get service URL
echo -e "${BLUE}Finding Cloud Run service...${NC}"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format="value(status.url)" 2>/dev/null || echo "")

if [ -z "$SERVICE_URL" ]; then
    echo -e "${RED}Error: Cloud Run service '$SERVICE_NAME' not found in region '$REGION'${NC}"
    echo -e "${YELLOW}Please deploy the service first using deploy.sh${NC}"
    exit 1
fi

echo -e "Service URL: ${GREEN}$SERVICE_URL${NC}"
echo ""

# Endpoint URL
ENDPOINT_URL="${SERVICE_URL}/api/scheduled-meetings/execute"

# Service account for Cloud Scheduler
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Region:         ${GREEN}$REGION${NC}"
echo -e "  Schedule:       ${GREEN}$SCHEDULE${NC} (every 2 minutes)"
echo -e "  Endpoint:       ${GREEN}$ENDPOINT_URL${NC}"
echo -e "  Service Account: ${GREEN}$SERVICE_ACCOUNT${NC}"
echo ""

# Enable Cloud Scheduler API
echo -e "${BLUE}Enabling Cloud Scheduler API...${NC}"
gcloud services enable cloudscheduler.googleapis.com --quiet

# Check if scheduler job already exists
if gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" --location="$REGION" &>/dev/null; then
    echo -e "${YELLOW}Scheduler job already exists. Updating...${NC}"

    gcloud scheduler jobs update http "$SCHEDULER_JOB_NAME" \
        --location="$REGION" \
        --schedule="$SCHEDULE" \
        --uri="$ENDPOINT_URL" \
        --http-method=POST \
        --oidc-service-account-email="$SERVICE_ACCOUNT" \
        --oidc-token-audience="$ENDPOINT_URL" \
        --quiet

    echo -e "${GREEN}✓ Scheduler job updated${NC}"
else
    echo -e "${BLUE}Creating new scheduler job...${NC}"

    gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" \
        --location="$REGION" \
        --schedule="$SCHEDULE" \
        --uri="$ENDPOINT_URL" \
        --http-method=POST \
        --oidc-service-account-email="$SERVICE_ACCOUNT" \
        --oidc-token-audience="$ENDPOINT_URL" \
        --quiet

    echo -e "${GREEN}✓ Scheduler job created${NC}"
fi

echo ""
echo -e "${GREEN}✓ Cloud Scheduler setup complete!${NC}"
echo ""
echo -e "${BLUE}Job Details:${NC}"
echo -e "  Name:     ${GREEN}$SCHEDULER_JOB_NAME${NC}"
echo -e "  Schedule: ${GREEN}Every 2 minutes${NC}"
echo -e "  Status:   ${GREEN}Active${NC}"
echo ""

# Show job status
echo -e "${BLUE}Current job configuration:${NC}"
gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" --location="$REGION"

echo ""
echo -e "${YELLOW}Note: The scheduler will check for pending meetings every 2 minutes${NC}"
echo -e "${YELLOW}and automatically join meetings that are scheduled to start.${NC}"
echo ""

# Offer to test
echo -e "${BLUE}Would you like to trigger a test run now? (y/N)${NC}"
read -p "> " TEST_RUN

if [[ "$TEST_RUN" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Running test execution...${NC}"
    gcloud scheduler jobs run "$SCHEDULER_JOB_NAME" --location="$REGION"
    echo ""
    echo -e "${GREEN}✓ Test run triggered${NC}"
    echo -e "${YELLOW}Check Cloud Run logs to see the execution:${NC}"
    echo -e "  gcloud run logs read --service=$SERVICE_NAME --region=$REGION --limit=50"
fi

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
