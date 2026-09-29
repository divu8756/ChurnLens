# ChurnLens: SPEC v1.3

## Objective
User uploads Excel/CSV customer data. A LangGraph pipeline acts as a
data analyst: cleans data, finds insights, quantifies churn drivers,
runs hypothesis tests with full calculations, predicts churn risk, and
recommends actions. Results appear in a 8-tab dashboard.

## Upload rules
- .csv, .xlsx only. Max 10 MB, max 100,000 rows, min 100 rows.
- Excel with several sheets: user picks one.
- UI warns: "Use anonymised or sample data only."
- Files stored per session under DATA_DIR/{session_id} as parquet.
Sessions older than 2 hours are deleted by a cleanup task.
- "Try sample data" loads the bundled IBM Telco Customer Churn CSV.

## State (Pydantic model, one key per producer)
session_id, sheet_name, raw_path, clean_path, schema, target_column,
positive_label, target_confirmed, id_columns, time_column,
cleaning_log, data_health, eda_results, segments, survival_results,
hypothesis_results, model_metrics, feature_importance, shap_summary,
odds_ratios, predictions_path, insights, recommendations,
impact_estimates, validation_report, report_paths,
errors: Annotated[list, add], progress: Annotated[list, add],
retry_counts: dict
Large data (dataframes, predictions) lives in files; state holds paths.

## Nodes (backend/app/agents/, one module each)
1. ingest_node: read the chosen sheet, validate limits, save parquet.
2. schema_agent: LLM sees ONLY column names, dtypes, 5 sample values,
null %, unique counts. Proposes column types, id columns, time
column, target column and positive label. Temperature 0.
3. human_review: interrupt() with the proposal; resume via
Command(resume={confirmed schema}). Validate the user's answer.
4. cleaning_node: coerce types (e.g. blank strings to NaN then numeric),
duplicates, missing values (median / mode / "Unknown"), outliers
flagged by IQR and z-score but only capped when documented. Every
action written to cleaning_log with row counts. Computes data_health.
5-8. Fan-out in parallel after cleaning:
5. eda_node: distributions, churn rate by each categorical (with n),
churned vs retained numeric comparisons, correlation matrix,
tenure bands.
6. segmentation_node: numeric features scaled, K-means k in 2..8 by
silhouette, segment profiles with size and churn rate.
7. survival_node: Kaplan-Meier overall and by top 3 categoricals,
log-rank p-values. Only if time_column exists (conditional edge).
8. hypothesis_node:
- Exclude id columns, the target, and categoricals with > 20 levels.
- Categorical: chi-square with H0/H1, observed, expected, per-cell
(O-E)^2/E, df, statistic, p, Cramér's V. If any expected count < 5:
Fisher's exact for 2x2, otherwise merge rare levels into "Other"
and note it.
- Numeric: Shapiro (sample of <= 5,000) + Levene, then Welch t-test
or Mann-Whitney U. Report means, medians, SDs, statistic, df, p,
Cohen's d or rank-biserial r.
- Benjamini-Hochberg across all tests. Store raw p, adjusted p,
alpha used, and a plain-English conclusion.
- Every step stored so the UI can show the full calculation.
9. modelling_node: exclude id columns; stratified 80/20 split, seed 42;
sklearn Pipeline (impute, scale, one-hot handle_unknown=ignore);
Logistic Regression (class_weight=balanced) + HistGradientBoosting;
5-fold CV on train; metrics on test once: accuracy, precision,
recall, F1, ROC-AUC, PR-AUC, confusion matrix, ROC points.
Permutation importance; SHAP (TreeExplainer on the GB model,
sample <= 2,000 rows); odds ratios with 95% CI from statsmodels
Logit on standardised numerics (state "per 1 SD"); per-customer
risk score, risk band, and top 3 SHAP reasons in plain English.
Leakage guard: fail with a clear error if test ROC-AUC > 0.99.
10. impact_node (Python, no LLM): for each candidate segment, compute
customers affected, current churn rate, revenue at risk (if a
revenue column exists), and impact under stated assumptions
(e.g. 10% and 25% relative churn reduction). These are the only
impact numbers recommendations may use.
11. insight_agent (LLM, temp 0): input = compact computed-results JSON.
Output: top 10 insights; each has text, figures[] with source_key
(dot path into state), significance flag, correlation-not-causation
note where relevant.
12. recommendation_agent (LLM, temp 0.3): problem (with data), action,
target segment, customers affected, impact (from impact_estimates
only, assumptions stated), priority (impact vs effort), group:
quick_win | medium_term | strategic. Every figure has source_key.
13. validator_node: for every figure, resolve source_key in state and
compare with tolerance (relative 1%, handle % vs fraction, rounding).
Also scan text for numbers not in figures[]. Fail: route back to the
failing agent with the list of bad figures; max 2 retries per agent,
then drop the offending items and log a warning.
14. report_node: PDF report + Excel (cleaned data, predictions, test
results) for Power BI.
15. error_node: fatal problems (no target, < 100 rows, single-class
target) end the run with a clear user-facing message.

## Edges
ingest -> schema_agent -> human_review -> cleaning
-> [eda, segmentation, survival?, hypothesis] (parallel)
-> modelling -> impact -> insight_agent -> recommendation_agent
-> validator -> (pass) report -> END
-> (fail) back to failing agent (max 2)
Any node -> error_node on fatal errors.

## Chat agent (separate graph)
ReAct agent with tools: get_stat, get_segment, get_test_result,
get_customer_risk, filter_and_aggregate (whitelisted: filter by
column/op/value, groupby, count, mean, median, sum; no exec/eval).
Answers only from tool results; says so if something wasn't computed.
Max 6 tool calls per question.

## Persistence and streaming
- Checkpointer: SqliteSaver at DATA_DIR/checkpoints.db locally;
PostgresSaver if DATABASE_URL is set. Keyed by thread_id=session_id.
- If a session is missing (server restarted), API returns 410 and the
UI shows "Session expired, please re-upload."
- SSE stream of node start/finish events + heartbeat every 15 s.

## Prompts
backend/app/prompts/<agent>.v1.md with: role, task, input schema,
output schema, rules, 1-2 few-shot examples. Core rule in every
analytical prompt: "Use only numbers from the provided JSON. Cite the
source_key for each figure. If a result is not statistically
significant, say so."

## API (FastAPI)
POST /upload, POST /sample, GET /stream/{id} (SSE),
POST /confirm-schema/{id}, GET /results/{id}, POST /chat/{id},
GET /export/{id}/pdf, GET /export/{id}/excel, GET /health.
CORS: only FRONTEND_ORIGIN. Rate limit /upload and /chat per IP.

## Frontend tabs
Executive Overview, Customer Insights, Churn Drivers, Hypothesis
Testing (expand for full KaTeX calculation, alpha adjustable),
Risk Predictions (filter, bands, CSV download), Recommendations,
Ask the Data. Plus upload screen, Data Health screen, schema
confirmation screen, and a live progress view.

## Deployment
GitHub monorepo /backend /frontend, MIT license, GitHub Actions
(ruff, pytest, frontend lint/typecheck/build). Backend: Dockerfile +
render.yaml. Frontend: Vercel, root directory frontend.

## Acceptance criteria
- Telco sample runs end to end; all tabs populated.
- Hypothesis results equal scipy within 1e-9 (unit tested).
- ROC-AUC >= 0.80 on Telco test set.
- Validator rejects a planted wrong number (unit tested).
- Graph pauses for schema confirmation and resumes correctly (tested).
- Live Vercel URL talking to the Render backend.

## MVP cut line
MVP = Phases 1-6 (all dashboard tabs except Experiments and Ask the Data).
Then 5b (next best offer), 5c (A/B testing), 7 (chat, exports), 8 (deploy).

## v1.2 additions (these override anything above that conflicts)

### LLM provider
- All LLM calls use Google Gemini via langchain-google-genai, through the
  single wrapper backend/app/llm.py (see CLAUDE.md rules 16-20).
- Tiers: "pro" = GEMINI_MODEL (insights, recommendations, experiment
  summary); "fast" = GEMINI_MODEL_FAST (schema detection, chat, offer
  messages). Throttle GEMINI_RPM. Tests never call the real API.

### Next best offer (Phase 5b)
- State adds: offer_columns, offer_catalog, offer_effectiveness,
  offer_recommendations_path.
- schema_agent (prompt v2) also proposes offer columns (offer_shown,
  offer_accepted, offer_date, offer_cost); the user confirms them in
  human_review together with offer costs and eligibility rules.
- offer_node runs after impact_node (conditional edge: skipped when no
  offer columns). Python only. Expected value per customer x offer:
  P(churn) * P(accept) * P(stay | accepted) * customer_value - offer_cost,
  with a "no offer" option. The LLM only writes the message, on demand.
- Risk Predictions tab adds "Next best offer" and "Expected value"
  columns and a "Why this offer" panel. Recommendations tab adds an
  "Offer performance" card group.

### A/B testing (Phase 5c)
- Experiments persist in a database (SQLAlchemy + Alembic; SQLite locally,
  Postgres when DATABASE_URL is set), NOT in session folders.
- Lifecycle: draft -> approved -> running -> results_uploaded -> decided.
  Approval and decision are human gates, recorded in an append-only
  audit log. Approved designs are locked.
- Sample size via statsmodels power analysis; hash-based randomisation;
  balance check; results analysis with SRM check, Wilson / Newcombe CIs,
  two-proportion z-test, intention-to-treat primary, guardrails,
  decision helper (ship / don't ship / inconclusive).
- Decided experiments feed measured effects into offer_node
  ("experiment-proven" vs "observational").
- New 8th tab: Experiments.

### Frontend tabs (final list)
Executive Overview, Customer Insights, Churn Drivers, Hypothesis Testing,
Risk Predictions, Recommendations, Experiments, Ask the Data.


## v1.3 additions: metrics layer (Phase 5d). These override earlier sections.

### Principles
- Python computes every number. The LLM only explains numbers present in
  state (via source_keys). The browser never computes metrics: edited
  assumptions are sent to the API, which recomputes in Python.
- Every output that depends on an assumption carries an "ASSUMPTIONS"
  block: name, value, unit, source ("default" | "user" | "data"), and a
  one-line meaning.

### Model metrics (held-out test set only)
- ROC-AUC, PR-AUC (= average precision), precision and recall at top 10%
  (k = ceil(0.10 * n_test), ties broken by stable sort), lift by decile
  (decile churn rate / overall churn rate) and cumulative gains,
  Brier score, calibration curve (10 uniform bins, with bin counts).
- Money metrics use CALIBRATED probabilities: CalibratedClassifierCV fitted
  on the training split only (isotonic if n_train >= 1000, else sigmoid,
  cv=5). Report Brier + calibration for raw AND calibrated.

### Business metrics
- Requires a confirmed monthly revenue (ARPU) column; if none, revenue
  metrics are disabled with a clear message (model metrics still work).
- revenue_at_risk_i = p_churn_i * ARPU_i * months_remaining
  (months_remaining default 12, user-editable, 1..60).
- Offer catalogue: backend/app/config/offers.yaml, validated by Pydantic:
  name, cost (per accepted offer), assumed_acceptance_rate (0..1),
  assumed_save_rate (0..1, P(stays | accepted), default 0.5),
  eligible_segments (list of rules: {column, in: [...]} or
  {column, min, max} or {risk_band: [...]}; empty list = everyone).
  Rules referencing a column not in the confirmed schema: that offer is
  skipped with a warning, never a crash.
- expected_saving_i,o = p_churn_i * acceptance_o * save_rate_o * ARPU_i
  * months_remaining - acceptance_o * cost_o
  (cost is paid only when the offer is accepted). Setting save_rate = 1
  and cost_basis = "per_targeted" reproduces the simpler formula
  p * acceptance * ARPU * 12 - cost. Choose the offer with the highest
  expected_saving; if <= 0, recommend "No offer".
- If Phase 5b/5c data-driven estimates exist for an offer, they replace the
  YAML assumptions and are labelled source = "data".
- Offer ROI by segment (risk band x plan type/contract, or confirmed
  segment column): customers, total expected saving, total expected cost,
  ROI = saving / cost.
- A/B plan: one shared function in backend/app/stats/experiment_design.py
  (also used by Phase 5c). Minimum detectable lift is RELATIVE:
  p2 = p1 * (1 - lift). p1 = observed churn rate of the target segment.
  n per arm via statsmodels proportion_effectsize (Cohen's h) +
  NormalIndPower.solve_power (alpha 0.05, power 0.8 default, two-sided),
  rounded up. Return the formula (LaTeX), every input, and the result.

### Telemetry
- State key telemetry_events: Annotated[list, operator.add]; every node is
  wrapped by a decorator that appends {node, started_at, latency_ms,
  status, retries, input_tokens, output_tokens, model}. Token counts come
  from the Gemini wrapper's usage metadata.
- Run summary: validator pass/fail counts, figures caught, retries per
  agent, schema corrections (fields where the human changed the AI's
  proposal), total latency, latency per node, tokens, estimated cost from
  backend/app/config/pricing.yaml (per-1M-token prices per model; defaults
  0 with note "free tier"; labelled ESTIMATE).
- Run summaries persist in the database (runs table) for trends.

### API additions
GET /metrics/model/{id}, GET /metrics/business/{id},
POST /metrics/business/{id} (body: assumptions; returns recomputed
metrics), GET /telemetry/{id}, GET /telemetry/runs?limit=50.

### Upload errors (HTTP 422, plain-English message + what to do)
- No binary target candidate ("No churn/target column found. Add a
  column with two values, e.g. Yes/No, and re-upload.")
- Target has one class only.
- Fewer than MIN_ROWS rows (config, default 100).

### Frontend
- New tabs: Model Performance, Business Impact, Agent Health.
  Model Performance takes over the metrics part of Churn Drivers (Churn
  Drivers keeps importance, SHAP, odds ratios).
- Charts in these tabs use Plotly (react-plotly.js with
  plotly.js-basic-dist-min, loaded via next/dynamic with ssr: false,
  through one shared PlotlyChart wrapper). Existing tabs keep Recharts.
- KPI cards have plain-English tooltips. Editable assumptions call
  POST /metrics/business/{id} (debounced 400 ms) and re-render. When
  assumptions differ from defaults, AI explanations show "Based on
  default assumptions" with a "Regenerate explanation" button (LLM +
  validator run again on the new numbers).

