#!/usr/bin/env bash
# Deploy the desk to Cloud Run. Creates billable resources; run it on purpose.
#
#   scripts/deploy.sh               # AI Studio key from .env, stored in Secret Manager
#   QUORUM_ENTERPRISE=1 scripts/deploy.sh   # Gemini Enterprise Agent Platform instead of a key
#
# Needs billing on the project. The account and project come from the environment
# or .env, never a default, so the script cannot fall back to a work account:
#
#   QUORUM_GCLOUD_ACCOUNT=you@example.com
#   QUORUM_GCLOUD_PROJECT=your-project-id
set -euo pipefail

# A value from the environment, else from .env.
from_env() {
  local value="${!1:-}"
  [ -n "$value" ] || value="$(grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"'" || true)"
  printf '%s' "$value"
}

ACCOUNT="$(from_env QUORUM_GCLOUD_ACCOUNT)"
PROJECT="$(from_env QUORUM_GCLOUD_PROJECT)"
[ -n "$ACCOUNT" ] && [ -n "$PROJECT" ] || { echo "Set QUORUM_GCLOUD_ACCOUNT and QUORUM_GCLOUD_PROJECT in .env" >&2; exit 1; }
REGION="${QUORUM_REGION:-us-central1}"
SERVICE="${QUORUM_SERVICE:-quorum}"
SA_NAME="quorum-run"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
SECRET="quorum-gemini-key"
USE_BQ="${QUORUM_USE_BIGQUERY:-}"
MIN_INSTANCES="${QUORUM_MIN_INSTANCES:-0}"

gcloud config set account "$ACCOUNT" >/dev/null
gcloud config set project "$PROJECT" >/dev/null

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com secretmanager.googleapis.com bigquery.googleapis.com

gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 \
  || gcloud firestore databases create --location="$REGION" --type=firestore-native

gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SA_NAME" --display-name="Quorum desk"
for role in roles/datastore.user roles/bigquery.jobUser roles/bigquery.dataViewer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${SA}" --role="$role" --condition=None >/dev/null
done

ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT},QUORUM_USE_FIRESTORE=on"
[ -n "$USE_BQ" ] && ENV_VARS="${ENV_VARS},QUORUM_USE_BIGQUERY=1"
SECRETS=()
if [ -n "${QUORUM_ENTERPRISE:-}" ]; then
  gcloud services enable aiplatform.googleapis.com
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${SA}" --role=roles/aiplatform.user --condition=None >/dev/null
  ENV_VARS="${ENV_VARS},GOOGLE_GENAI_USE_ENTERPRISE=true,GOOGLE_CLOUD_LOCATION=global"
else
  KEY="$(from_env GEMINI_API_KEY)"
  [ -n "$KEY" ] || { echo "No GEMINI_API_KEY in the environment or .env" >&2; exit 1; }
  gcloud secrets describe "$SECRET" >/dev/null 2>&1 || gcloud secrets create "$SECRET" --replication-policy=automatic
  printf '%s' "$KEY" | gcloud secrets versions add "$SECRET" --data-file=- >/dev/null
  gcloud secrets add-iam-policy-binding "$SECRET" --member="serviceAccount:${SA}" --role=roles/secretmanager.secretAccessor >/dev/null
  SECRETS=(--set-secrets "GEMINI_API_KEY=${SECRET}:latest")
fi

# One instance: uploads and live hearing streams are held in memory, and it caps spend.
# No CPU throttling: a hearing keeps running to its seal after the browser disconnects.
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --service-account "$SA" \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 \
  --timeout 900 \
  --concurrency 40 \
  --min-instances "$MIN_INSTANCES" --max-instances 1 \
  --no-cpu-throttling \
  --set-env-vars "$ENV_VARS" \
  ${SECRETS[@]+"${SECRETS[@]}"} \
  --quiet

gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
