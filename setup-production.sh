#!/bin/bash
#
# Meeting Transcription - Production Mode Setup
# Run this after deploying to enable webhook security and production mode
#

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       Enable Production Mode with Webhook Security            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Cloud Run service exists
echo -e "${BLUE}Checking for existing deployment...${NC}"
echo ""

SERVICE_EXISTS=$(gcloud run services describe meeting-transcription --region us-central1 --format="value(metadata.name)" 2>/dev/null || echo "")

if [ -z "$SERVICE_EXISTS" ]; then
    echo -e "${RED}❌ Cloud Run service 'meeting-transcription' not found${NC}"
    echo ""
    echo "Please run ./setup.sh first to deploy your service."
    exit 1
fi

echo -e "${GREEN}✓ Found meeting-transcription service${NC}"
echo ""

# Get project info
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SERVICE_URL=$(gcloud run services describe meeting-transcription --region us-central1 --format="value(status.url)")

echo -e "${BLUE}Your webhook URL:${NC}"
echo ""
echo -e "  ${GREEN}${SERVICE_URL}/webhook/recall${NC}"
echo ""
echo "Before continuing, make sure you've set up the webhook in Recall.ai:"
echo ""
echo "  1. Go to: https://recall.ai/dashboard/webhooks"
echo "  2. Click 'Add Webhook' and paste the URL above"
echo "  3. Enable these events:"
echo "     • bot.joining_call"
echo "     • bot.done"
echo "     • bot.call_ended"
echo "     • recording.done"
echo "     • transcript.done"
echo "     • transcript.failed"
echo "  4. Click Save"
echo "  5. Copy the webhook secret (starts with whsec_)"
echo ""
read -p "Have you completed these steps? [Y/n]: " READY
READY=${READY:-Y}

if [[ ! "$READY" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Please complete the webhook setup in Recall.ai first, then run this script again."
    exit 0
fi

# Get webhook secret
echo ""
echo -e "${BLUE}Enter your Recall.ai Webhook Secret${NC}"
echo ""
read -sp "Paste your webhook secret (hidden, starts with whsec_): " WEBHOOK_SECRET
echo ""

if [ -z "$WEBHOOK_SECRET" ]; then
    echo -e "${RED}❌ No webhook secret provided${NC}"
    exit 1
fi

if [[ ! "$WEBHOOK_SECRET" =~ ^whsec_ ]]; then
    echo ""
    echo -e "${YELLOW}⚠️  Warning: Webhook secret should start with 'whsec_'${NC}"
    echo ""
    read -p "Continue anyway? [y/N]: " CONTINUE
    CONTINUE=${CONTINUE:-N}
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Store in Secret Manager
echo ""
echo -e "${BLUE}Storing webhook secret in Secret Manager...${NC}"
echo ""

if gcloud secrets describe RECALL_WEBHOOK_SECRET --format="value(name)" 2>/dev/null; then
    echo "Secret already exists, adding new version..."
    echo -n "$WEBHOOK_SECRET" | gcloud secrets versions add RECALL_WEBHOOK_SECRET --data-file=-
else
    echo "Creating new secret..."
    echo -n "$WEBHOOK_SECRET" | gcloud secrets create RECALL_WEBHOOK_SECRET --data-file=-
fi

echo -e "${GREEN}✓ Webhook secret stored${NC}"
echo ""

# Grant permissions
echo "Granting Cloud Run service account access to secret..."
gcloud secrets add-iam-policy-binding RECALL_WEBHOOK_SECRET \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet 2>/dev/null || true

echo -e "${GREEN}✓ Permissions granted${NC}"
echo ""

# Update Cloud Run service
echo -e "${BLUE}Updating Cloud Run service...${NC}"
echo ""
echo "This will:"
echo "  • Add the webhook secret to your service"
echo "  • Remove ENV=development (enable production mode)"
echo ""

gcloud run services update meeting-transcription \
    --region us-central1 \
    --update-secrets='RECALL_WEBHOOK_SECRET=RECALL_WEBHOOK_SECRET:latest' \
    --remove-env-vars=ENV \
    --quiet

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    ✅ WEBHOOKS SECURED! ✅                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Webhook signature verification is now ENABLED${NC}"
echo ""
echo "Your service will now:"
echo "  ✅ Verify all webhook requests from Recall.ai"
echo "  ✅ Reject webhooks with invalid signatures"
echo "  ✅ Run in production mode"
echo ""
echo -e "${BLUE}Test your webhook:${NC}"
echo "  1. Schedule a test meeting in your web interface"
echo "  2. Check Cloud Run logs for webhook events"
echo "  3. Look for: '✅ Valid webhook signature'"
echo ""
echo "Done! 🎉"
echo ""
