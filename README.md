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

## Limitations

- Recommendations show association, not proven causation; validate with an A/B
  test before rollout.
- Offer results compare customers who accepted an offer with those who
  declined it. Acceptors choose to accept, so their lower churn is not proof the
  offer caused it; a randomised holdout group measures the real effect.
- Churn risk scores are not calibrated yet, so expected values are estimates.
- Use anonymised or sample data only.

MIT licensed.
