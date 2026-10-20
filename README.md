# Multimodal Analyst

Analyze any listed company from its **financial statements (PDF), market data and news,
product images, earnings-call audio and marketing videos** with Google's multimodal
Gemini models, then cross-check everything in a strategic synthesis.

Apple's Q2 FY24 results ship as a one-click demo set.

```
Browser (React + Vite, Firebase Hosting, Firebase Auth)
   │  POST /api/analyses/*  →  Server-Sent Events (status, tool calls, data, text)
   │  PUT  signed URL       →  Cloud Storage (user uploads, deleted after 7 days)
   ▼
FastAPI on Cloud Run ──► Gemini (google-genai SDK, Gemini Enterprise Agent Platform)
                     └─► Alpha Vantage (function calling)
```

| Analysis | Input | How |
| --- | --- | --- |
| Market & news | Ticker | Gemini function calling over Alpha Vantage: quote, fundamentals, 6-month weekly prices, news sentiment. Price chart rendered from the raw series. |
| Financial statement | PDF | Gemini extracts figures into a typed schema → **ratios computed in Python** (with balance checks) → Gemini explains them. |
| Pricing | Image | Per-product price comparison across markets. |
| Earnings call | Audio / video | Takeaways, guidance and tone per speaker. |
| Marketing | Video | Scene breakdown, selling strategy, emotional appeal. |
| Synthesis | The above | Contradictions between filings, management and news; strategy recommendations. Uses a Pro model with automatic fallback to Flash. |

Models are configuration, not code: `MODEL_DEFAULT` (default `gemini-3.8-flash`) and
`MODEL_SYNTHESIS` (default `gemini-3.1-pro-preview`).

## Local development

Requires Python 3.12+, Node 22+, and Application Default Credentials for a project with
the Vertex AI / Agent Platform API enabled (`gcloud auth application-default login`).

```bash
# API on :8080
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env       # set GOOGLE_CLOUD_PROJECT, ALPHA_VANTAGE_API_KEY
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8080

# Web app on :5173 (proxies /api to :8080; no sign-in when VITE_FIREBASE_API_KEY is empty)
cd frontend && npm install && npm run dev
```

## Tests

```bash
cd backend && ../.venv/bin/pytest            # unit + API tests, no network
cd backend && RUN_LIVE_TESTS=1 ../.venv/bin/pytest -m live   # real Gemini; checks extraction
                                                             # of the demo PDF against printed figures
cd frontend && npm test                      # Vitest + Testing Library
```

CI (`.github/workflows/ci.yml`) runs lint, type checks, tests, the Docker build and the web build.

## Deploy

1. Create or pick a Firebase project (it is also the GCP project), enable **Authentication →
   Google** sign-in, and add a web app.
2. Put its web config in `frontend/.env.production` (`firebase apps:sdkconfig web`), using the
   `VITE_FIREBASE_*` names from `frontend/.env.example`.
3. Run:

```bash
PROJECT_ID=your-project ./infra/deploy.sh          # setup + API + web
PROJECT_ID=your-project ./infra/deploy.sh api      # redeploy API only
PROJECT_ID=your-project ./infra/deploy.sh web      # redeploy web only
```

The script creates a least-privilege service account, an upload bucket with CORS and a
7-day lifecycle, stores the Alpha Vantage key in Secret Manager, deploys Cloud Run with
`AUTH_REQUIRED=true`, and publishes the web app to Firebase Hosting.

The browser calls Cloud Run directly (not through a Hosting rewrite) because Hosting
rewrites time out after 60 seconds and buffer responses, which breaks streaming video
analyses.

## Security notes

- Every analysis/upload route verifies a Firebase ID token.
- Gemini only reads demo assets or the caller's own `uploads/<uid>/` objects, so the
  service account can't be used to read other files.
- Uploads go straight to Cloud Storage via 15-minute signed URLs with the exact size signed in.
- Model output is rendered as Markdown without raw HTML.
- `--max-instances 3` caps spend; tune it for your quota.
