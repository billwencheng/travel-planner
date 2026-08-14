#!/bin/bash
# Enable essential GCP APIs required for local development and Vertex AI Agent Engine.

set -e

if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set."
    echo "Please set it via: export GOOGLE_CLOUD_PROJECT='your-project-id'"
    exit 1
fi

echo "Enabling core APIs for project: $GOOGLE_CLOUD_PROJECT..."

gcloud services enable \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    iam.googleapis.com \
    --project="$GOOGLE_CLOUD_PROJECT"

echo "APIs enabled successfully!"
