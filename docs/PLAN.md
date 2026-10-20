# Modernization plan

Rewrite of the original single-file Streamlit app (Gemini 1.5 Flash, Apple-only, no tests)
into a deployable frontend + backend. The original is in git history (the first commit).

## Decisions

- General "analyze any company" tool; Apple Q2 FY24 kept as the demo set.
- React + Vite frontend on Firebase Hosting with Firebase Auth (Google sign-in).
- FastAPI backend on Cloud Run, `google-genai` SDK (the `vertexai.generative_models`
  module was removed on 2026-06-24).
- Default model `gemini-3.8-flash`; synthesis on `gemini-3.1-pro-preview` with fallback.
- Streamlit app deleted.

## Fixed from the original

| Original problem | Now |
| --- | --- |
| `ALPHA_VANTAGE=os.getenv(key)` used the secret as an env var *name*, so the key was `None` | Secret mounted by Cloud Run as `ALPHA_VANTAGE_API_KEY` |
| Hard-coded project, secret path and `/home/theone/...` PDF path | All configuration via env (`backend/app/config.py`) |
| "6-month price evolution" with only `GLOBAL_QUOTE` (today's price) | `TIME_SERIES_WEEKLY` tool + chart |
| Tool loop read only `parts[0]` | All parallel function calls handled, model turn kept verbatim (thought signatures) |
| Gemini computed ratios | Gemini extracts, Python computes, balance checks run, period mismatches flagged |
| Overall report depended on Streamlit session state and tab order | Synthesis takes whatever analyses are done and says which are missing |
| Retired `gemini-1.5-flash`, Python 3.8 image, no tests | Current models via config, Python 3.12, 61 backend + 11 frontend tests |

## Phases

| # | Phase | Status |
| --- | --- | --- |
| 0 | Repo, tooling, CI | ✅ |
| 1 | Backend: config, Gemini wrapper, 5 analyses + synthesis, SSE, tests | ✅ |
| 2 | Statement extraction + deterministic ratios + live eval | ✅ (live eval needs credentials to run) |
| 3 | Frontend: company/ticker, demo/upload sources, streaming cards, chart, ratios table | ✅ |
| 4 | Persistence: save reports per user in Firestore, history page, share link | ⏳ |
| 5 | Deploy: Cloud Run + Firebase Hosting + Auth (`infra/deploy.sh`) | ✅ written, not yet run |
| 6 | Extras: Google Search grounding with citations for news, voice Q&A on the earnings call (Live API), PDF export, Playwright e2e, per-user rate limits | ⏳ |
