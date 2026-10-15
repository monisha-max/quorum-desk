#!/usr/bin/env bash
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
REGION="${QUORUM_REGION:-us-central1}"
SERVICE="${QUORUM_SERVICE:-quorum}"

gcloud config set account you@example.com
gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com firestore.googleapis.com || true

gcloud firestore databases create --location="$REGION" --type=firestore-native || true

NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
SA="${NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/aiplatform.user" \
  --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/datastore.user" \
  --condition=None >/dev/null

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --quiet \
  --memory 1Gi \
  --timeout 300 \
  --min-instances 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_ENTERPRISE=true,QUORUM_MODEL=gemini-2.5-flash"

gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
