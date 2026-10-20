# Run Instructions — Multimodal Analyst

Company analysis from filings, market data, news, images, audio and video with
Google's multimodal Gemini models. A FastAPI backend streams each analysis over
Server-Sent Events to a React front-end; a final synthesis cross-checks them.
Apple's Q2 FY24 results ship as a one-click demo set.

```
ticker ──► market agent     Gemini function calling over Alpha Vantage
PDF    ──► statement        Gemini extracts figures → Python computes ratios → Gemini explains
image  ──► pricing          ┐
audio  ──► earnings call    ├ Gemini reads the file from Cloud Storage
video  ──► marketing        ┘
all of the above ──► synthesis (Pro model, falls back to Flash)
```

---

## 1. Layout

```
backend/
  app/main.py                FastAPI app factory, CORS, /api/health
  app/config.py              All settings (env vars), including model IDs
  app/llm.py                 google-genai wrapper behind an `LLM` protocol (tests fake it)
  app/analyses/market.py     Manual function-calling loop over Alpha Vantage tools
  app/analyses/statement.py  Extract → compute → comment
  app/analyses/media.py      Image / audio / video presets
  app/analyses/synthesis.py  Cross-analysis report with model fallback
  app/analyses/common.py     Event types, MediaRef, media access policy, system prompt
  app/finance/statement.py   Extraction schema Gemini fills in
  app/finance/ratios.py      Deterministic ratio maths + consistency checks
  app/tools/alpha_vantage.py Async Alpha Vantage client
  app/api/                   Routes: analyses (SSE), uploads (signed URLs), demo, auth deps
  tests/                     61 tests + 2 live tests; Gemini and Alpha Vantage faked
  requirements.txt           Runtime dependencies (serving image)
  requirements-dev.txt       + pytest, respx, ruff, mypy
  pyproject.toml             Tool configuration only (pytest, ruff, mypy)
  Dockerfile                 Cloud Run image, non-root
  .env.example
frontend/
  src/App.tsx                Company/ticker bar, five analysis cards, synthesis
  src/lib/api.ts             fetch + SSE streaming, signed-URL upload
  src/lib/sse.ts             Incremental SSE parser
  src/lib/firebase.ts        Firebase Auth (optional in local dev)
  src/hooks/useAnalysis.ts   Reducer turning events into card state
  src/components/            Cards, source picker, ratios table, price chart
  src/**/*.test.ts(x)        11 tests (Vitest + Testing Library)
  .env.example
infra/deploy.sh              Cloud Run + Firebase Hosting setup and deploy
firebase.json                Hosting config (SPA rewrite, security headers)
.github/workflows/ci.yml     Lint, type checks, tests, Docker and web builds
docs/PLAN.md                 Modernization plan and what changed from the Streamlit version
```

---

## 2. Prerequisites

- **Python 3.12+** and **Node 22+**
- A **Google Cloud project** with the Vertex AI / Gemini Enterprise Agent
  Platform API enabled
- An **Alpha Vantage** API key (free): <https://www.alphavantage.co/support/#api-key>
- Optional for local runs: a Firebase project (sign-in) and a Cloud Storage
  bucket (uploads). Without them the app runs with no sign-in and demo files only.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd frontend && npm install)
gcloud auth application-default login
```

---

## 3. Configuration

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### Backend (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | — | Project billed for Gemini |
| `GOOGLE_CLOUD_LOCATION` | `global` | Gemini 3.x models are served from the global endpoint |
| `MODEL_DEFAULT` | `gemini-3.8-flash` | All analyses |
| `MODEL_SYNTHESIS` | `gemini-3.1-pro-preview` | Synthesis; falls back to `MODEL_SYNTHESIS_FALLBACK` |
| `ALPHA_VANTAGE_API_KEY` | — | Market card. Without it the card returns a clear error |
| `UPLOAD_BUCKET` | — | Enables uploads. Without it only demo files are offered |
| `AUTH_REQUIRED` | `true` | Set `false` for local runs without Firebase |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list of allowed web origins |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Cloud Run URL. Leave empty locally — Vite proxies `/api` to `:8080` |
| `VITE_FIREBASE_*` | Firebase web config. Leave `VITE_FIREBASE_API_KEY` empty to skip sign-in |

---

## 4. Run it

```bash
# Terminal 1 — API on :8080
cd backend && uvicorn app.main:app --reload --port 8080

# Terminal 2 — web app on :5173
cd frontend && npm run dev
```

Open <http://localhost:5173>, keep the Apple demo files, and run the cards in
any order. The synthesis button enables once at least one analysis is done.

### Endpoints

```bash
curl localhost:8080/api/health
# {"status":"ok","model":"gemini-3.8-flash","uploads":false,"auth":false}

curl localhost:8080/api/demo

curl -N -X POST localhost:8080/api/analyses/market \
  -H 'Content-Type: application/json' -d '{"ticker":"AAPL"}'

curl -N -X POST localhost:8080/api/analyses/media -H 'Content-Type: application/json' \
  -d '{"media":[{"uri":"gs://bucket-15-storage/pricing.jpeg","mime_type":"image/jpeg"}],
       "task":"pricing","company":"Apple"}'
```

Every analysis responds with an SSE stream of `status`, `tool_call`, `data`
(`prices`, `statement`, `ratios`), `delta` (Markdown text), then `done` or `error`.

---

## 5. Tests

```bash
cd backend && pytest -q                 # 61 passed, 2 skipped — no network, no credentials
cd frontend && npm test                 # 11 passed
```

The backend injects a scripted `FakeLLM` (`tests/conftest.py`) and an
`httpx.MockTransport` for Alpha Vantage, so the suite needs no Google or Alpha
Vantage access. Ratio tests use Apple's printed FY24 Q2 figures.

### Live checks

```bash
cd backend && RUN_LIVE_TESTS=1 pytest -m live
```

Calls real Gemini: a smoke call, and an extraction of the demo PDF compared
field-by-field with the printed figures. Run it after changing `MODEL_DEFAULT`.

### Linting

```bash
cd backend && ruff check . && mypy app            # mypy runs in strict mode
cd frontend && npm run lint && npm run typecheck
```

---

## 6. Docker

```bash
docker build -t multimodal-analyst-api backend
docker run --rm -p 8080:8080 --env-file backend/.env --user "$(id -u)" \
  -v ~/.config/gcloud/application_default_credentials.json:/tmp/adc.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json multimodal-analyst-api
```

The mount gives the container your local application-default credentials.
`--user` is needed because gcloud writes that file with mode 600, so the
image's own `appuser` (uid 10001) cannot read it. On Cloud Run the service
account is used instead and none of this applies.

### Cloud Run + Firebase Hosting

```bash
PROJECT_ID=your-project ./infra/deploy.sh          # setup + API + web
PROJECT_ID=your-project ./infra/deploy.sh api      # API only
PROJECT_ID=your-project ./infra/deploy.sh web      # web only (needs frontend/.env.production)
```

---

## 7. Troubleshooting

| Symptom | Cause |
|---|---|
| Card shows "The server has no valid Google Cloud credentials for Gemini" | Run `gcloud auth application-default login`, or mount credentials into the container (§6) |
| `Gemini request failed (404)` | Model ID retired or not enabled in the project/location — change `MODEL_*` |
| Market card: "ALPHA_VANTAGE_API_KEY is not configured" | Key missing in `backend/.env` |
| Market card: "Alpha Vantage: … rate limit …" | Free tier allows 25 requests/day; one market run uses up to ~6 |
| "Price chart unavailable" but the report still appears | Weekly series call failed; the model can still answer from the other tools |
| `403 Media must be a demo asset or one of your uploads` | Intended — see §8 |
| "Upload your own" is greyed out | `UPLOAD_BUCKET` unset (`/api/health` → `"uploads": false`) |
| Upload fails in the browser with a CORS error | Bucket CORS not set for this origin; `infra/deploy.sh setup` configures it |
| Every API call returns 401 locally | `AUTH_REQUIRED` defaults to `true`; set it `false` or configure Firebase |
| Synthesis says "Written by gemini-3.8-flash" | The Pro preview model failed and the fallback answered |

---

## 8. Before you change anything

- **Gemini never does the arithmetic.** `statement.py` asks for figures in the
  `FinancialStatement` schema, `finance/ratios.py` computes every ratio, and the
  commentary prompt says not to recalculate. Moving maths back into a prompt
  makes the numbers untestable.
- **Balance sheet comparisons are not year-over-year.** Apple's statement
  compares March 2024 with September 2023 (fiscal year end), while the income
  statement compares quarter with quarter. `compute_ratios` adds a note when the
  dates differ, and ROA/ROE report only the current period.
- **Keep the model turn verbatim in the tool loop.** `market.py` appends
  `response.candidates[0].content` unchanged because Gemini 3 needs its thought
  signatures back, and it answers *every* function call in a turn, matching
  `id`s. `tests/test_market.py` fails if either regresses.
- **`check_media` is the only thing stopping Gemini from reading arbitrary
  objects.** The service account can read whatever its IAM allows; the API only
  forwards `gs://` URIs under the demo prefix or `uploads/<caller uid>/`.
- **Expected errors become an SSE `error` event; unexpected ones become
  "Unexpected server error"** with the detail only in the server log
  (`api/analyses.py`). Don't put exception text from unknown errors in the stream.
- **The browser calls Cloud Run directly, not through a Hosting rewrite.**
  Hosting rewrites time out at 60 s and buffer the response, which breaks
  streaming of long video analyses.
- **Model IDs live only in `config.py`.** There are no hard-coded model names
  elsewhere — keep it that way so a retirement is an env change.
- **`SourcePicker` defaults to the demo file until the user chooses.** The demo
  manifest loads after the first render; deciding the mode once at mount left
  every card stuck on "upload" (`App.test.tsx` covers it).
