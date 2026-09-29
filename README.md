# ChurnLens

Agentic churn analysis: upload customer data (CSV or Excel) and get cleaning,
statistics, hypothesis tests, churn risk scores and recommended actions in a
dashboard. Work in progress; see `docs/PROGRESS.md`.

- `backend/`: FastAPI + LangGraph (Python 3.14)
- `frontend/`: Next.js (TypeScript, Tailwind)

## Run locally

```bash
cd backend && python3.14 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env   # then fill in the values
.venv/bin/uvicorn app.main:app --reload
```

```bash
cd frontend && npm install && cp .env.example .env.local && npm run dev
```

MIT licensed.
