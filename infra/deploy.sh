#!/usr/bin/env bash
# One-time setup + deploy of the API (Cloud Run) and the web app (Firebase Hosting).
# Safe to re-run: existing resources are left as they are.
#
#   PROJECT_ID=my-project ./infra/deploy.sh            # everything
#   PROJECT_ID=my-project ./infra/deploy.sh api        # only the Cloud Run service
#   PROJECT_ID=my-project ./infra/deploy.sh web        # only Firebase Hosting
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-multimodal-analyst-api}"
SA_NAME="${SA_NAME:-multimodal-analyst}"
UPLOAD_BUCKET="${UPLOAD_BUCKET:-${PROJECT_ID}-analyst-uploads}"
WEB_ORIGINS="${WEB_ORIGINS:-https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com}"
TARGET="${1:-all}"

SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
gc() { gcloud --project "$PROJECT_ID" "$@"; }

setup() {
  echo "==> Enabling APIs"
  gc services enable run.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com \
    storage.googleapis.com identitytoolkit.googleapis.com firebasehosting.googleapis.com

  echo "==> Service account $SA"
  gc iam service-accounts describe "$SA" >/dev/null 2>&1 ||
    gc iam service-accounts create "$SA_NAME" --display-name "Multimodal Analyst API"
  gc projects add-iam-policy-binding "$PROJECT_ID" --condition=None --quiet \
    --member "serviceAccount:$SA" --role roles/aiplatform.user >/dev/null
  # Signed upload URLs are signed through IAM signBlob as the service account itself.
  gc iam service-accounts add-iam-policy-binding "$SA" --quiet \
    --member "serviceAccount:$SA" --role roles/iam.serviceAccountTokenCreator >/dev/null

  echo "==> Upload bucket gs://$UPLOAD_BUCKET"
  gc storage buckets describe "gs://$UPLOAD_BUCKET" >/dev/null 2>&1 ||
    gc storage buckets create "gs://$UPLOAD_BUCKET" --location "$REGION" \
      --uniform-bucket-level-access --public-access-prevention
  local cors lifecycle
  cors="$(mktemp)" lifecycle="$(mktemp)"
  python3 - "$WEB_ORIGINS" >"$cors" <<'PY'
import json, sys
origins = [o for o in sys.argv[1].split(",") if o] + ["http://localhost:5173"]
print(json.dumps([{"origin": origins, "method": ["PUT"], "maxAgeSeconds": 3600,
                   "responseHeader": ["Content-Type", "x-goog-content-length-range"]}]))
PY
  # Uploads are working copies; delete them after a week.
  echo '{"rule":[{"action":{"type":"Delete"},"condition":{"age":7}}]}' >"$lifecycle"
  gc storage buckets update "gs://$UPLOAD_BUCKET" --cors-file "$cors" --lifecycle-file "$lifecycle"
  rm -f "$cors" "$lifecycle"
  gc storage buckets add-iam-policy-binding "gs://$UPLOAD_BUCKET" \
    --member "serviceAccount:$SA" --role roles/storage.objectAdmin >/dev/null

  echo "==> Secret ALPHA_VANTAGE_API_KEY"
  if ! gc secrets describe ALPHA_VANTAGE_API_KEY >/dev/null 2>&1; then
    read -rsp "Alpha Vantage API key: " key && echo
    printf '%s' "$key" | gc secrets create ALPHA_VANTAGE_API_KEY --data-file=-
  fi
  gc secrets add-iam-policy-binding ALPHA_VANTAGE_API_KEY --quiet \
    --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor >/dev/null
}

deploy_api() {
  echo "==> Deploying Cloud Run service $SERVICE"
  local env_file
  env_file="$(mktemp)"
  python3 - "$PROJECT_ID" "$UPLOAD_BUCKET" "$WEB_ORIGINS" >"$env_file" <<'PY'
import json, sys
project, bucket, origins = sys.argv[1:]
env = {
    "GOOGLE_CLOUD_PROJECT": project,
    "GOOGLE_CLOUD_LOCATION": "global",
    "UPLOAD_BUCKET": bucket,
    "AUTH_REQUIRED": "true",
    "CORS_ORIGINS": json.dumps([o for o in origins.split(",") if o]),
}
for k, v in env.items():
    print(f"{k}: {json.dumps(v)}")
PY
  # Public at the HTTP layer (browsers call it directly); every API route checks the
  # Firebase ID token. Long timeout for video analysis; max instances caps spend.
  gc run deploy "$SERVICE" --source "$ROOT/backend" --region "$REGION" \
    --service-account "$SA" --allow-unauthenticated \
    --env-vars-file "$env_file" \
    --set-secrets ALPHA_VANTAGE_API_KEY=ALPHA_VANTAGE_API_KEY:latest \
    --timeout 900 --concurrency 20 --cpu 1 --memory 1Gi \
    --min-instances 0 --max-instances 3 --cpu-boost
  rm -f "$env_file"
  gc run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)'
}

deploy_web() {
  local api_url
  api_url="$(gc run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"
  echo "==> Building web app against $api_url"
  if [[ ! -f "$ROOT/frontend/.env.production" ]]; then
    echo "Missing frontend/.env.production with the VITE_FIREBASE_* web config." >&2
    echo "Get it with: firebase apps:sdkconfig web --project $PROJECT_ID" >&2
    exit 1
  fi
  (cd "$ROOT/frontend" && npm ci && VITE_API_BASE_URL="$api_url" npm run build)
  echo "==> Deploying Firebase Hosting"
  (cd "$ROOT" && firebase deploy --only hosting --project "$PROJECT_ID")
}

case "$TARGET" in
  all) setup; deploy_api; deploy_web ;;
  setup) setup ;;
  api) deploy_api ;;
  web) deploy_web ;;
  *) echo "Unknown target: $TARGET (all|setup|api|web)" >&2; exit 2 ;;
esac
