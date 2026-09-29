# ChurnLens progress

Project root: /Users/divyanshusrivastava/ChurnLens

## Current task
Phase 4 gate

## Next step
Phase 4 gate: review, end-to-end Telco run on a live server, PR, CI, merge. Then T5.1.

## Done
- Bootstrap: plan, spec, rules, settings, data generators and backend/.env unpacked.
- Preflight: tools checked, Gemini models selected, gh logged in, secret check in place.
- Sample data generated: telco_churn.csv (7,014 rows = 7,000 unique + 14 duplicates,
  11 blank TotalCharges) and the 4-table India dataset (git-ignored, regenerate
  with scripts/generate_india_sample.py).
- T1.1: architecture restated, Mermaid flow, top 5 risks (docs only, no tests).
- T1.2: FastAPI skeleton (/health, CORS, fail-fast settings), Dockerfile
  (python:3.14-slim, non-root), Next.js 16 app (TS strict, Tailwind, ESLint,
  lint/typecheck/build scripts), home page shows Backend online/offline
  (verified in a browser against a local backend), CI workflow, MIT license,
  .env.example files. Backend 4 tests.
- T1.3: public repo already existed (divu8756/ChurnLens); phase-1 pushed, CI green
  (backend + frontend jobs). No .env file tracked.
- T1.4: backend/app/llm.py wrapper (tiers, shared throttle, retries with
  backoff + jitter honouring retryDelay, content-failure retry, zero-quota 429
  not retried, optional fallback model, token logging without prompts, usage
  listeners), app/llm_fake.py FakeLLM, scripts/gemini_smoke_test.py.
  Backend 27 tests passing.
- Phase 1 gate review: fixed (Medium) wrong-type LLM output raised
  ValidationError outside the content-retry path; fixed (Medium) relative
  DATA_DIR resolved against the working directory instead of backend/.
  Docker image built and checked (/health ok, runs as non-root user "app").
  Backend 29 tests. Low, not fixed: "INTERNAL" substring match in
  is_transient is broad; frontend has no unit tests yet (vitest arrives in T6.1).
- Phase 1 merged to main (PR #1, CI green).
- T2.1: ChurnState (Pydantic, reducers on errors/progress/telemetry_events),
  graph builder with all 16 nodes as stubs, safe_node wrapper (FatalNodeError
  routes to error_node, other errors are recorded and the run continues,
  interrupt() passes through), conditional survival/offer edges, validator
  retry routing, SQLite checkpointer factory (Postgres behind DATABASE_URL,
  driver installed at deploy time), docs/graph.md. Backend 38 tests.
- T2.2: POST /upload (extension + real content checks, size, row limits,
  latin-1 fallback, duplicate columns renamed with a warning, ragged rows
  rejected), multi-sheet xlsx flow (choose_sheet then POST
  /upload/{id}/sheet), POST /sample, parquet under DATA_DIR/sessions/{id},
  2-hour cleanup loop, session ids validated against path traversal,
  ingest_node. Backend 61 tests.
- T2.3: prompts/schema_agent.v1.md (+ minimal prompt loader, full T5.2
  version later), stats/profiling.py (profile with <= 5 samples, id/target/
  time/type heuristics; floats and numbers-as-text never flagged as ids),
  schema_agent node (fast tier, temp 0, 30 s; rules win on ids; AI target
  and positive label only accepted if valid for the data; falls back to rules
  on LLM failure). Heuristics alone get Telco fully right (customerID id,
  Churn/Yes target, tenure time column, TotalCharges numeric). Backend 73 tests.
- T2.4: human_review node (interrupt only, no side effects before it),
  schema validation (binary target, positive label, id/time columns),
  RunManager (background thread per session, events with ids), POST
  /analyze/{id} (added: explicit, idempotent run start), POST
  /confirm-schema/{id} (422 with problem list, 409 if not paused or resumed
  twice, 410 unknown), GET /stream/{id} SSE (node_start/finish, error,
  awaiting_confirmation, resumed, done, 15 s heartbeat, Last-Event-ID
  reconnect). Checkpoint serializer registers state types; tests run with
  LANGGRAPH_STRICT_MSGPACK. pytest-timeout added (60 s). Backend 87 tests.
- T2.5: stats/cleaning.py + cleaning_node: numeric coercion (blank ->
  missing), trim/collapse spaces, unify case to the most common spelling,
  exact duplicates, target -> 0/1, missing target rows dropped, categorical
  blanks -> "Unknown", rare invalid negatives -> missing, IQR/z outlier
  flags (never changed), data_health with documented 0-100 score, fatal on
  one class or < MIN_ROWS. Telco: 11 TotalCharges blanks, 14 duplicates,
  7,000 rows, InternetService case fixed, 5 negative call minutes. 103 tests.
- Phase 2 gate review: fixed (Medium) exact duplicates were removed even
  without an ID column, where identical rows can be different customers;
  now only flagged. Fixed (Medium) .xlsx zip bomb: workbooks that unpack to
  > 200 MB are rejected. Clearer "too few rows" message. Edge cases checked:
  one column, all-null column, non-English headers, 100k rows (cleaning
  2.6 s). End-to-end on a live server: sample -> analyze -> paused with
  AI proposal (ai+rules, ~50 s Gemini latency) -> confirm -> cleaning (7,000
  rows, health 81) -> stubs -> done. Backend 105 tests.
- Phase 2 merged to main (PR #2, CI green).
- T3.1: stats/eda.py + eda_node: overview, numeric summaries (churned vs
  retained, histograms), churn rate by level with n (sorted, > 20 levels
  folded into Other), Pearson correlation on numerics + with target, tenure
  bands when a time column exists; strict-JSON output. 115 tests.
- T3.2: stats/segmentation.py + segmentation_node: numeric features (no id,
  target, time, constant columns), median impute + scale, K-means k=2..8
  (n_init 10, seed 42) chosen by silhouette (<= 5,000-row sample), profiles
  (size, % of base, churn rate and lift, means, z-scores), auto labels from
  top-2 features; per-customer labels saved to segments.parquet (not state);
  skip path under 2 features. 123 tests.
- T3.3: stats/survival.py + survival_node (lifelines): KM overall and for the
  top 3 categoricals by Cramer's V (2-6 levels, groups >= 5 rows), median
  (or "not reached"), survival at 6/12/24 (null beyond follow-up), 95% CI,
  multivariate log-rank per variable, curves <= 200 points. KM and log-rank
  equal lifelines called directly. 132 tests.
- T3.4: stats/hypothesis.py + hypothesis_node: chi-square (no Yates, stated
  explicitly), Fisher for sparse 2x2, rare-level merging into Other,
  Shapiro (<= 5,000 sample) + Levene then Welch t (Cohen's d) or
  Mann-Whitney (rank-biserial r), BH across tests, H0/H1, assumptions, why,
  inputs, LaTeX steps with numbers, effect bands, conclusions; cap 40 tests;
  constant/>20-level columns skipped. All equal scipy/statsmodels within
  1e-9. Telco: Contract strongest (V 0.37), 28 of 40 significant. 146 tests.
- Phase 3 gate: 100k-row timings clean 2.1 s, EDA 0.4 s, segmentation
  5.1 s, survival 0.4 s, hypothesis 0.7 s. Real nodes run in parallel inside
  the graph (run tests). No High/Medium issues found; Low items are in Known
  issues (treatment columns, test cap order).
- Phase 3 merged to main (PR #3, CI green).
- T4.1: stats/modelling.py + modelling_node: features exclude ids, target,
  datetimes, text and treatment columns (offer_columns from 5b); stratified
  80/20 split before fitting; LR (balanced) vs HistGradientBoosting
  (balanced) by 5-fold CV PR-AUC on train; one test evaluation (accuracy,
  precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix, ROC <= 100
  points); leakage guard (> 0.99 fatal, |r| or V > 0.9 warning);
  permutation importance on original columns; model saved with joblib.
  Telco (treatments excluded): LR chosen, test ROC-AUC 0.829, PR-AUC 0.611;
  top drivers Contract, tenure, InternetService. 154 tests.
- T4.2: stats/explain.py: SHAP on the chosen model (TreeExplainer, else
  shap.Explainer with 100-row background; Telco LR -> LinearExplainer),
  one-hot SHAP summed back to original features, global mean |SHAP| +
  beeswarm points; statsmodels Logit odds ratios on train (per 1 SD / vs
  most frequent level, 95% CI), singular and separated terms dropped with
  a note; driver_impact table (permutation rank, SHAP, OR + CI, BH p) in
  feature_importance. Explanation failures are non-fatal. ORs equal
  statsmodels within 1e-9. Telco: Two year vs Month-to-month OR 0.08. 164 tests.
- T4.3: stats/predictions.py: every customer scored by the chosen model
  (probability 3 dp), bands from RISK_HIGH/RISK_MEDIUM (0.6/0.3), top 3
  SHAP reasons as text ("Contract: Month-to-month (+0.18)"), sorted by risk,
  written to predictions.parquet; band counts in model_metrics.risk_bands.
  GET /results/{id}: all result keys (server paths stripped), predictions
  100 per page, filter by band, 410/409/422 errors; works from the
  checkpoint after a restart. Fixed: SHAP column map crashed when a model
  had no categorical columns. 173 tests.

## Decisions
- Mode: FULL-AUTO (see CLAUDE.md AUTOPILOT).
- Project root is ~/ChurnLens (not ~/Documents/ChurnLens), linked to the
  public repo github.com/divu8756/ChurnLens. T1.3 reuses this repo instead of
  creating "churnlens".
- Python 3.14.5 (human's choice, replaces 3.11). backend/.venv is built from
  /usr/local/bin/python3.14. All backend dependencies resolve to prebuilt
  wheels on 3.14 (checked with a pip dry run). Dockerfile uses python:3.14-slim.
- Tool versions: Python 3.14.5, Node v24.16.0, git 2.50.1, gh 2.101.0.
  Homebrew is not installed; nothing needed installing.
- Gemini models (scripts/select_gemini_models.py, newest stable, non-preview)
  first chose GEMINI_MODEL=gemini-2.5-pro, GEMINI_MODEL_FAST=gemini-3.8-flash.
  Smoke test (T1.4): gemini-2.5-pro returns 404 for this key, and every Pro
  model (gemini-pro-latest, gemini-3.1-pro-preview) has free-tier quota 0.
  Enabling billing is a paid-service decision for the human, so both tiers use
  gemini-3.8-flash for now, with GEMINI_MODEL_FALLBACK=gemini-3.5-flash for
  when 3.8-flash is overloaded (it returned 503s during testing).
- SPEC's single "schema" state key is split into schema_proposal
  (schema_agent) and confirmed_schema (human_review): one producer per key,
  and "schema" would shadow a Pydantic BaseModel attribute. Fatal errors are
  ErrorEntry(fatal=True) in the shared errors list rather than a separate key.
- Runs live in memory in one API process (RunManager). A restart loses them
  and /stream answers 410 "Session expired"; fine for one Render instance.
- Cleaning does NOT median-impute numeric blanks (SPEC says median/mode/
  "Unknown"): imputing before the train/test split leaks test data, and some
  blanks are meaningful (NPS, AvgResolutionDays). The model pipeline imputes
  medians on the training split; stats tests drop missing values per test.
- SHAP explains the chosen model (runbook said the gradient boosting model):
  per-customer reasons must explain the model that produced the score.
- pandas pinned to 2.3.3 (not 3.x): lifelines 0.30.3 requires pandas < 3.
  The full suite passes on 2.3.3.
- Port 8000 is taken by another local program; use --port 8010 locally if needed.
- Sample data is synthetic and IBM-Telco-style (fixed seed 20260331); India
  4-table demo dataset (fixed seed 20260401).

### T1.1 Architecture restated
1. A user uploads a CSV/XLSX (100 to 100,000 rows, <= 10 MB) or loads the Telco sample;
   it is stored as parquet under DATA_DIR/{session_id} and deleted after 2 hours.
2. A LangGraph StateGraph runs the analysis; state holds small JSON results and
   file paths, never dataframes. Checkpoints go to SQLite (Postgres if DATABASE_URL).
3. schema_agent (Gemini fast tier) sees only column metadata and 5 sample values,
   and proposes types, id/time/target columns and the positive label.
4. human_review interrupts the graph; the user confirms or edits the schema in the UI
   and the graph resumes with Command(resume=...).
5. Pure-Python stats run after cleaning: EDA, segmentation, survival (only with a
   time column) and hypothesis tests fan out in parallel, then modelling (LR + HGB,
   SHAP, odds ratios, calibrated risk scores) and impact estimates.
6. Gemini (pro tier) only writes insights and recommendations from a compact
   digest; every figure cites a source_key into state.
7. validator_node checks every figure and every number in the text against state,
   sending failures back to the agent (max 2 retries), then drops bad items.
8. Later phases add next best offer, A/B experiments (SQLAlchemy DB), a metrics
   layer with telemetry, a chat agent with whitelisted tools, and PDF/Excel exports.
9. FastAPI exposes upload, SSE progress, schema confirmation, results, metrics,
   chat and export endpoints; CORS is limited to FRONTEND_ORIGIN.
10. The Next.js dashboard (Recharts, Plotly for metrics tabs, KaTeX) only displays
    numbers from the API; backend on Render (Docker), frontend on Vercel.

### T1.1 LangGraph flow
```mermaid
flowchart TD
    START([START]) --> ingest
    ingest --> schema_agent --> human_review
    human_review -->|interrupt / resume| cleaning
    cleaning --> eda & segmentation & hypothesis
    cleaning -->|time_column set| survival
    eda & segmentation & hypothesis & survival --> modelling
    modelling --> impact
    impact -->|offer columns| offer
    impact -->|no offer columns| insight_agent
    offer --> insight_agent
    insight_agent --> recommendation_agent --> validator
    validator -->|pass| report --> END([END])
    validator -->|fail, retries < 2| insight_agent
    validator -->|fail, retries < 2| recommendation_agent
    ingest & schema_agent & cleaning & modelling -.->|fatal| error_node --> END
```

### T1.1 Top 5 risks and mitigations
1. Gemini free-tier rate limits (429) and slow calls stall the pipeline.
   Mitigation: shared token-bucket throttle, backoff honouring retry delay,
   deterministic fallbacks so the dashboard renders without LLM output.
2. The LLM invents or misquotes numbers. Mitigation: digest-only inputs,
   figures[] with source_keys, a strict validator with text number scanning,
   retry loop capped at 2, drop failing items.
3. Statistical errors (wrong test choice, Yates correction, BH, leakage).
   Mitigation: pure stats functions unit-tested against scipy/statsmodels at
   1e-9, leakage guard (ROC-AUC > 0.99), campaign columns excluded as treatments.
4. Python 3.14 is newer than the plan assumed; some libraries (shap/numba,
   lifelines) may have edge-case bugs. Mitigation: pinned versions that
   resolve to wheels, full test suite in CI on 3.14, fall back to
   shap.Explainer if TreeExplainer fails.
5. Graph state and parallel fan-out bugs (concurrent writes, resume re-running
   side effects, large state). Mitigation: one key per producer, reducers on
   shared lists, human_review does nothing before interrupt(), files for
   large data, tests for fan-out merge and resume.

## Checkpoints for the human
- S1 (T1.1): architecture summary, graph flow and risks are under Decisions above.
- S4 (T1.4): real smoke test via the wrapper succeeded on gemini-3.8-flash
  (answer "ready", 14 input / ~200 output tokens, 19-32 s latency because the
  model "thinks"; it also returned 503 overloaded several times and the
  wrapper's retries handled it). Pro models need billing: if you enable it
  in Google AI Studio, set GEMINI_MODEL=gemini-3.1-pro-preview (or a stable
  Pro when one exists) in backend/.env.

## Known issues
- Gemini Flash models often return 503 "high demand" (both 3.8 and 3.5 at
  the same time during T2.3). The schema agent then uses rules only, which
  are correct on Telco. Consider billing / another model if this persists.
- Campaign/offer columns (OfferCost, CampaignGroup...) are treatments, not
  customer traits. They still enter segmentation and hypothesis tests until
  Phase 5b confirms offer_columns; then exclude them from segmentation and
  the churn model (runbook T4.1 / data dictionary).
- Hypothesis test cap (40) keeps columns in data order; with more candidates
  the last ones are skipped (Telco: OfferCost).
- Per-IP rate limiting on /upload and /chat (SPEC API section) is not built
  yet; planned for Phase 8 hardening.

## Human actions needed
- S7 at the end: Render + Vercel dashboard steps (paste GEMINI_API_KEY into Render yourself).
