# ChurnLens progress

Project root: /Users/divyanshusrivastava/ChurnLens

## Current task
T8.1 (Production hardening)

## Next step
Open the Phase 7 PR (phase-7 is pushed; gh is not installed in this
environment, so use the GitHub link or install gh), stacked on phase-5d (#9)
which is stacked on phase-5c (#8); the human merges them in order. Then
Phase 8: T8.1 production hardening (per-IP limits on /upload and the other
LLM endpoints, reuse app/ratelimit.py), T8.2 deploy (HUMAN STOP S7), T8.3
README + demo assets.

## Phase 5d plan (T5d.0; S8 recorded as a checkpoint, FULL-AUTO)

### 1. Files and functions
- backend/app/stats/model_metrics.py (new, pure, dict in / dict out):
  `roc_auc(y, p) -> float`; `pr_auc(y, p) -> float` (average precision);
  `at_top(y, p, share=0.10) -> {k, precision, recall}` (k = ceil(share*n),
  stable sort by -p); `deciles(y, p) -> [{decile, n, churners, churn_rate,
  lift, cumulative_gain}]`; `brier(y, p) -> float`; `calibration(y, p,
  bins=10) -> [{bin, low, high, n, mean_predicted, observed_rate}]`;
  `evaluate(y, p) -> dict` (all of the above); `calibrate(pipeline, x_train,
  y_train) -> (model, method)` (CalibratedClassifierCV(clone, isotonic if
  n_train >= 1000 else sigmoid, cv=5), fitted on the training split only);
  `model_metrics_v2(artifacts, frame, schema) -> (metrics, calibrated_all)`.
- backend/app/stats/modelling.py: ModelArtifacts gains `calibrated` (the
  fitted calibrator) and `calibration_method`.
- backend/app/agents/modelling.py: writes `model_metrics_v2`; predictions
  gain `churn_probability_raw`; `churn_probability` becomes the calibrated
  value (rule 23: money metrics and NBO use it). SHAP reasons still explain
  the raw model (ranking). Risk bands move to calibrated probabilities
  (closes the Phase 4 known issue: 32% High vs ~25% churn).
- backend/app/config.py -> backend/app/config/__init__.py (package, same
  imports) + app/config/offers.yaml + app/config/pricing.yaml (package data).
- backend/app/catalog.py (new): Pydantic `OfferSpec {name, cost,
  cost_basis: per_accepted|per_targeted, assumed_acceptance_rate,
  assumed_save_rate=0.5, eligible_segments: [Rule]}`, `Rule =
  {column, in} | {column, min, max} | {risk_band: [...]}`;
  `load_catalogue(path) -> list[OfferSpec]` raising `CatalogueError` with
  the YAML line of the problem; `load_pricing(path) -> Pricing`.
- backend/app/stats/business_metrics.py (new): `revenue_at_risk(df, p,
  arpu_col, months_remaining=12) -> dict`; `eligible_offers(customer,
  catalogue, columns) -> (offers, warnings)`; `expected_saving(p, arpu,
  months, offer) -> float`; `next_best_offer(df, p, arpu_col, catalogue,
  months) -> table + summary` (best, runner-up, "No offer" when best <= 0);
  `offer_roi_by_segment(nbo_table, segment_col) -> [...]`; `ab_plan(segment
  frame, lift, alpha, power) -> dict`; `business_metrics(state values,
  assumptions) -> dict` (everything + ASSUMPTIONS, or {enabled: false,
  reason} without an ARPU column); `data_overrides(offer_effectiveness,
  evidence) -> {offer: {acceptance, save_rate, source="data"}}` from Phase
  5b rates and Phase 5c evidence.
- backend/app/stats/experiment_design.py: `sample_size_two_proportions(p1,
  relative_lift, alpha=0.05, power=0.8, ratio=1.0) -> dict` (shares the
  maths of `sample_size`).
- backend/app/graph/telemetry.py (new): `traced(name, fn) -> fn` wrapping
  every node inside safe_node (one event per run incl. failed/skipped);
  per-node token capture through a contextvar + llm usage listener;
  `schema_corrections(proposal, confirmed) -> {count, fields}`;
  `summarise_run(values, pricing) -> dict`; `save_run(summary)`,
  `list_runs(workspace, limit)`.
- backend/app/experiments/models.py + migration 0007: `RunSummary` table
  (session_id, workspace_hash, created_at, summary JSON).
- backend/app/api/metrics.py (new) and app/api/telemetry.py (new).
- backend/app/api/upload.py + app/ingest.py: 422s for no binary target
  candidate and one class only (MIN_ROWS exists already).
- backend/app/prompts/business_explanation.v1.md + app/agents/
  business_explanation.py: 3 validated sentences on the business metrics
  (the "Regenerate explanation" button; cached per assumptions hash).
- frontend: components/charts/plotly-chart.tsx; components/model-performance/
  *, components/business-impact/*, components/agent-health/*; lib/metrics.ts
  (display helpers only); dashboard tabs; Churn Drivers loses its metrics
  cards; e2e opens the three tabs and edits one assumption.

### 2. State, API, config
- State: `model_metrics_v2: JsonDict | None` (modelling_node);
  `business_metrics: JsonDict | None` (impact_node, default assumptions);
  `telemetry_events` already exists (operator.add, parallel-safe).
- GET /metrics/model/{id} -> ModelMetricsV2; GET /metrics/business/{id} ->
  BusinessMetrics (defaults); POST /metrics/business/{id} body
  BusinessAssumptions {months_remaining 1..60, offers: {name: {acceptance,
  save_rate, cost}}, relative_lift 0.01..0.9, alpha, power} -> recomputed
  BusinessMetrics (no LLM); POST /metrics/business/{id}/explain ->
  validated explanation; GET /telemetry/{id} -> RunSummary; GET
  /telemetry/runs?limit=50 -> [RunSummary] (workspace-scoped).
- offers.yaml example:
  ```yaml
  - name: 10% loyalty discount (3 mo)
    cost: 15
    assumed_acceptance_rate: 0.35
    assumed_save_rate: 0.5
    eligible_segments: [{risk_band: [High, Medium]}]
  - name: Annual contract switch bonus
    cost: 40
    assumed_acceptance_rate: 0.2
    eligible_segments: [{column: Contract, in: [Month-to-month]}]
  ```
- pricing.yaml: `note: free tier; prices: {<model>: {input_per_1m: 0,
  output_per_1m: 0}}`, default 0, labelled ESTIMATE.

### 3. Reuse vs new
Reused: the Phase 4 stratified split (ModelArtifacts.train_index /
test_index, seed 42), predictions parquet, stats/experiment_design.py
(Phase 5c), Phase 5b offer_effectiveness rates and Phase 5c offer_evidence
(workspace-scoped) as "data" overrides, llm usage listeners (Phase 1),
the experiments database for the runs table. New: model_metrics.py,
calibration, catalogue/pricing YAML, business_metrics.py, telemetry.py,
metrics/telemetry APIs, Plotly wrapper and three tabs.

### 4. Risks
- Calibrating class-weighted models: calibrate a clone of the chosen
  pipeline with CalibratedClassifierCV on the training split only; the
  test split is only used to report raw vs calibrated Brier (asserted
  index-disjoint).
- No ARPU column: business metrics return {enabled: false, reason}; model
  metrics, A/B plan (churn only) and telemetry still work.
- offers.yaml rules on absent columns: skip that offer with a warning.
- Parallel telemetry writes: events go through the operator.add reducer;
  token attribution uses a contextvar per node run, not globals.
- Stale LLM explanations after assumption edits: explanation cached by an
  assumptions hash; the UI shows "Based on default assumptions" + a
  Regenerate button whenever the shown numbers differ from the explained
  ones.
- Plotly bundle / SSR: plotly.js-basic-dist-min imported only in the
  browser inside one wrapper. Deviation: no react-plotly.js (it requires
  the full plotly.js as a peer, which npm would install); the wrapper calls
  Plotly.react / purge itself.
- Calibrated probabilities change risk bands and NBO values: fixtures that
  cite them (E2E cites impact_estimates only) are re-checked.

### 5. Tests and reference values
- T5d.1: ROC-AUC, PR-AUC, Brier, calibration_curve(n_bins=10) equal sklearn
  at 1e-9; precision/recall@10% and decile lift on a hand-worked 20-row
  fixture with ties (k = 2); calibrator fitted on train indices only
  (disjoint from test); calibrated Brier <= raw Brier on Telco.
- T5d.2: 5-row fixture with hand-computed revenue_at_risk and every
  customer x offer expected_saving; "No offer" when all <= 0; ineligible
  offers excluded; missing-column rule -> warning; save_rate 1 +
  per_targeted reproduces p*acc*ARPU*12 - cost; months linear; invalid
  YAML -> CatalogueError with line number; no ARPU -> disabled.
- T5d.3: p1 0.20, lift 0.25 -> 903 per arm (statsmodels 902.34); p1
  0.26, lift 0.20 -> 1038; bad lift / p1 / power -> ValueError; ratio
  matches solve_power(ratio=...).
- T5d.4: parallel nodes append events (no InvalidUpdateError); every node
  incl. skipped has latency; token sums match a mocked wrapper; cost by
  hand; schema corrections on a fixture; summaries persist and list.
- T5d.5: each endpoint happy path, 410 unknown session, 422 invalid
  assumptions; uploads with no churn column, one class, 49 rows and
  MIN_ROWS - 1 rows -> 422 with the SPEC messages.
- T5d.6: component tests (KPI tooltips, ASSUMPTION labels, banner +
  Regenerate), PlotlyChart loads client-side only; E2E opens the three
  tabs and edits months remaining.

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
- Phase 4 gate: live end-to-end Telco run: analysis 10.8 s after
  confirmation, LR test ROC-AUC 0.831, bands High 2,239 / Medium 1,862 /
  Low 2,899, /results payload 324 KB. Fixed (Medium): schema proposal took
  ~68 s when Gemini was overloaded; structured_call now takes max_attempts
  and the schema agent uses 2 (the rules fallback is good). 174 tests.
- Phase 4 merged to main (PR #4, CI green).
- T5.1: graph/paths.py (dot-path resolver, longest dict key wins so column
  names with dots work), graph/results_digest.py (facts {key, value, label}
  for data health, churn by category, segments, significant + 5 strongest
  non-significant tests, model, drivers, survival, impact; <= 12k tokens,
  Telco ~10.6k), stats/impact.py + impact_node (segments and high-churn
  levels of significant categoricals: customers, churners, churn rate, lift,
  monthly revenue at risk, 10%/25% what-if scenarios with assumption text).
  Optional revenue_column added to the schema (heuristic: MonthlyCharges /
  ARPU names; validated numeric). tests/pipeline.py builds a full Telco
  state from the real nodes. 182 tests.
- T5.2: prompts insight_agent.v1.md and recommendation_agent.v1.md (role,
  task, input/output schema, rules incl. source_key citation, significance,
  "associated with", impact only from impact_estimates, priority = impact vs
  effort; worked examples on a tiny fictional digest; {{feedback}} slot).
  Loader tests. 189 tests.
- T5.3: agents/llm_agents.py: insight_agent (pro, temp 0) and
  recommendation_agent (pro, temp 0.3) with Pydantic structured output
  (Figure{source_key, value, display}; enums for effort/group; priority
  1-5; <= 10 insights, <= 8 recommendations), digest-only prompts,
  validator feedback injected as "Fix these issues", empty list + error on
  LLM failure. 195 tests.
- T5.4: app/validation.py + validator_node: source_key must resolve and be
  numeric; value and display match (1% rel / 0.005 abs, fraction vs
  percent); every standalone number in text fields must be a declared
  figure ("5G", "Q1", "90d" ignored; "< 0.001" accepted when true);
  recommendation impact must cite impact_estimates. Failing agents get
  feedback and are retried (max 2 each); then failing items are dropped.
  Validator writes its own final_insights / final_recommendations (one
  producer per key). Graph loop test: bad recommendation -> retried with
  feedback -> passes. 209 tests.
- T5.5: scripts/run_telco_live.py, report in docs/runs/phase5_telco_run.md.
  Final run: 131 s, 11 Gemini attempts (~101k input / ~13k output tokens,
  cost estimate 0 on the free tier), schema proposal ai+rules, validator
  11/15 verified, 4 dropped (3 unlisted numbers, 1 group mismatch).
  Fixes found by the live runs: validator read scientific notation
  (1.171e-202) as "202" (fixed + prompt asks for "< 0.001"); a
  recommendation could pair one group's customers with another group's
  impact (validator now requires the same impact group); a failed retry
  wiped the agent's previous answer (now kept so only bad items drop).
  212 tests.
- Phase 5 merged to main (PR #5, CI green; merged by the human).
- T6.1: backend app/api/contract.py (SSE event payloads, SchemaProposalOut,
  ResultsResponse, PredictionsPage, error bodies) declared in OpenAPI;
  /results has a response model; /stream also accepts ?after=<id> because a
  re-created browser EventSource cannot send Last-Event-ID (the header still
  wins). scripts/export_openapi.py -> frontend/openapi.json, and
  `npm run gen:types` -> lib/api-types.ts (openapi-typescript); a backend
  test fails if the snapshot is stale. lib/api.ts: typed calls for every
  endpoint, 30 s timeout, ApiError kinds (expired 410, conflict, validation
  with problems, client, server, timeout, network). lib/progress.ts (pure
  reducer) + lib/use-progress-stream.ts (EventSource, resume after last id,
  5 reconnects in a row with backoff, 410 probe -> expired, closes on done
  and unmount). vitest in CI. Fixed a flaky backend test: test_runs left
  background runs going into the next test's fake LLM; the fixture now waits
  for them. Backend 215 tests, frontend 29 tests.
- T6.2: upload page (drag-drop, browser type/size checks, sheet picker,
  Try sample data, anonymised-data warning), /analysis/[sessionId] (starts
  the run idempotently, so a reload re-attaches), live progress stepper
  (parallel nodes side by side; skipped/failed/waiting shown), schema
  confirmation (type per column, ID = type "ID", target + positive-label
  picker from new proposal.label_options, time and revenue pickers, AI
  reasoning, local checks + server 422 problems inline), Data Health
  (score + formula, row counts, class balance, missing % chart in Recharts,
  cleaning log). Loading/empty/error/expired states; no horizontal scroll at
  375 px. Backend: results.data_health / cleaning_log typed in the contract.
  Checked in a browser against a live backend on the Telco sample: rules
  fallback proposal, confirm, Data Health after cleaning (score 81,
  7,014 -> 7,000 rows), run done (10 insights, 5 recommendations, 12/15
  verified), offer skipped, reload re-attaches, fake session -> expired, the
  stream resumed once with ?after=4. Backend 216 tests, frontend 39 tests.
- T6.3a: dashboard shell (components/dashboard/dashboard.tsx: accessible
  tabs with arrow keys, a TABS registry each later tab adds to; Data Health
  is a tab too) shown when the run is done. Executive Overview
  (components/overview/): 5 KPI cards with plain-English tooltips
  (customers, churn rate, high-risk count, monthly revenue at risk, test
  ROC-AUC), top 3 insights with significance badges, top 3 recommendations
  by priority, validator badge (passed/checked, dropped), risk-band bar
  chart with axis titles and a caption. lib/format.ts (%, 2 dp stats,
  p < 0.001, counts, money), lib/palette.ts (Okabe-Ito). Contract types
  model_metrics, impact_estimates, validation_report (extra keys pass
  through) and reuses the agents' Insight/Recommendation models. Live check
  on Telco (111 s run, 11/15 verified): KPIs 7,000 / 25.66% / 2,239 /
  142,056 / 0.83; 375 px has no horizontal scroll. Backend 218, frontend 49 tests.
- T6.3b: Churn Drivers tab (components/drivers/): test metrics table with
  plain meanings + CV model comparison, confusion matrix, ROC curve with
  chance line, permutation importance bars with ± 1 SD whiskers, SHAP dot
  plot (Okabe-Ito blue-to-vermillion by value), odds-ratio forest plot on a
  log axis with 95% CI whiskers (15 strongest terms, dropped terms listed),
  driver summary table, leakage warning banner. Contract types the confusion
  matrix, ROC, cv, leakage warnings, feature_importance, shap_summary
  ("global" served under its real name) and odds_ratios. lib/drivers.ts
  (ordering, whiskers, log axis, deterministic jitter) is unit-tested. Live
  check on Telco fixed three display bugs (ROC ticks rounded 0.25 to 0.3,
  forest axis clipped CI whiskers, long labels cut off). Backend 219,
  frontend 56 tests.
- T6.3c: Hypothesis Testing tab (components/hypothesis/): tests sorted by
  adjusted p, statistic + df, "< 0.001" p-values, effect size with band,
  alpha slider (0.001-0.1) re-deriving significance as p_adjusted < alpha
  (BH adjustment does not depend on alpha) with a live count, rows expand
  into H0/H1, why this test, assumption checks, observed/expected tables or
  group stats, KaTeX formulas with substituted numbers, and the conclusion
  (server text at its alpha, explained at other alphas). katex 0.18 added
  (CLAUDE.md stack). Contract types hypothesis_results; found and fixed
  df typed as int (Welch df is fractional). Backend: LaTeX steps now use
  tex() (1.171 \times 10^{-202} instead of 1.171e-202) and \text{} for
  words. Live check: 28/40 significant at 0.05, 26/40 at 0.001, 10 KaTeX
  blocks, no errors, no horizontal scroll. Backend 222, frontend 63 tests.
- T6.3d: Risk Predictions tab (components/predictions/). New backend
  app/api/predictions.py: GET /predictions/{id} (50 per page, band filter,
  case-insensitive literal ID search, typed PredictionRow) so paging does
  not refetch the 300 KB results; GET /predictions/{id}/csv streams the
  same filter as an attachment, neutralising cells that start with = + - @
  (CSV injection from uploaded IDs/values). UI: band filter pills with
  counts, 300 ms debounced search, previous page kept visible while the
  next loads, reasons as chips (▲ raises / ▼ lowers risk, sign taken from
  the server text), pagination, Download CSV link. The finished analysis
  view now unmounts the progress/Data Health grid instead of hiding it.
  Live check: 2,899 Low rows, search "yqz" -> 8944-YQZDP, CSV matches the
  filter, 375 px no horizontal scroll. Backend 226, frontend 70 tests.
- T6.3e: Recommendations tab (components/recommendations/): cards grouped
  Quick wins / Medium-term / Strategic (fixed order, empty groups hidden),
  sorted by priority, each with problem, action, who, customers affected,
  impact labelled from its impact_estimates key (monthly revenue kept /
  fewer churners) with the stated assumption, and effort; validator badge;
  bar chart of customers reached per recommendation coloured by group.
- T6.3f: Customer Insights tab (components/insights/): top 10 insights with
  non-significant ones visibly marked (dashed border, badge, note); churn
  rate by category (column picker ordered by test evidence, overall-rate
  line); churned vs retained mean/median; segment cards (size, churn rate,
  lift, most distinctive features by z); Kaplan-Meier curves overall or by
  group with medians and log-rank p; correlation heatmap of the 12 columns
  most correlated with churn (diverging Okabe-Ito colours). Contract types
  eda_results, segments, survival_results (survival is null when there is
  no time column: the graph skips the node). formatStat no longer prints
  "-0.0". Live check fixed a heatmap clipped to 4 columns and uneven column
  widths, and a legend overlapping the axis label. Tab order now follows
  SPEC. Backend 227, frontend 82 tests.
- T6.4: Playwright E2E (frontend/e2e/telco.spec.ts, playwright.config.ts,
  `npm run e2e`): real API via scripts/e2e_server.py with a FakeLLM (rules
  schema; one insight and one recommendation that cite real deterministic
  Telco values and pass the real validator; LLM env forced to placeholders)
  plus a production build on :3100. Flow: sample -> confirm schema -> Data
  Health -> dashboard -> every tab with key assertions (7,000 / 25.66%,
  KaTeX, band filter, CSV link, recommendation impact) -> no console
  errors. ~20 s locally. New CI job `e2e` on PRs to main (report uploaded
  on failure). @playwright/test 1.63 added (runbook).
- Phase 6 gate review: fixed (Medium) /results validated the whole payload
  in one go, so one result key with an unexpected shape would 500 the entire
  dashboard; now a bad key is omitted with an error entry and the rest
  loads (tested). No High issues. Low items added to Known issues. Backend
  228, frontend 82 unit tests, E2E 1 (all green locally).
- Phase 6 merged to main (PR #6; merged by the human).
- T5b.1: ConfirmedSchema.offer_columns (OfferColumns: shown, accepted, date,
  cost, group, other; validated: columns exist, not target/ID/time/revenue,
  paired lists), written to state by human_review. Offer/campaign columns
  are treatments: feature_columns() now excludes them everywhere (EDA,
  segmentation, hypothesis tests, model). Heuristic likely_offer_columns
  (offer/promo/campaign/coupon/clicked/accepted/redeemed names) finds Telco's
  OfferShown/Accepted/Date/Cost + CampaignGroup (+ channel, clicked as other).
  Schema prompt v2 (v1 kept) adds flat offer fields; rules win, the AI only
  fills empty fields with real, unreserved columns. stats/offers.py:
  reshape_offers() turns all three layouts (one name column + Yes/No,
  delimited lists with ; , | or newline, one 0/1 column per offer) into the
  same long table (customer_id, offer, accepted, offer_date); names trimmed
  and case-unified (ties go to the spelling that sorts first); blanks = no
  offer; offer_catalog() lists only offers in the data (Telco: 6). Schema
  screen gets a "Retention offers" section (edit/clear, "offer" tag on
  columns). Telco effect: 35 hypothesis tests (23 significant) instead of
  40 with the cap hit; campaign columns excluded from the model; the run
  routes through the offer step (still a stub). Backend 238, frontend 86,
  E2E 1.
- T5b.2: offer effectiveness (app/stats/offers.py + app/agents/offer.py,
  offer_node registered). Cleaning no longer fills blanks in offer columns
  with "Unknown" (blank = no offer). Leakage filter: offers dated after the
  observation cutoff (a date column named snapshot/as-of/cutoff/extract) are
  dropped; a missing offer date or cutoff column gives a visible warning.
  Per offer (and per segment): shown, accepted, acceptance rate, churn among
  acceptors vs decliners with n; never-offered vs offered churn. Accepted x
  churned per offer (chi-square, Fisher when sparse; >= 20 shown) runs in
  the hypothesis step, kind "offer", in the same BH family (equal to scipy
  within 1e-9). Selection-bias check: mean predicted churn of offered vs
  never-offered; warns at a gap >= 0.05. Telco: 6 offers, 0 dropped
  (cutoff SnapshotDate); 10% loyalty discount significant (acceptors 27.9%
  vs decliners 44.6% churn, adj. p 0.0007); device upgrade credit not
  (matches the data dictionary); bias warning fires (57.3% vs 37.0% risk:
  offers were targeted by an old risk score). Backend 244.
- T5b.3: next best offer (app/stats/nbo.py, run by offer_node; settings
  NBO_HORIZON_MONTHS 12, NBO_MAX_DISCOUNT 0.20, NBO_DECLINE_DAYS 30).
  P(accept): per offer with >= 50 shown an unweighted logistic regression on
  the churn model's features (5-fold CV ROC-AUC reported), else the
  Laplace-smoothed segment acceptance rate flagged "low data". Expected value
  per Medium/High-risk customer x eligible offer with "No offer" when all are
  negative; discount cap and recent-decline rules. Best offer, runner-up and
  every input go to next_best_offers.parquet; /predictions and the CSV join
  best offer, expected value and runner-up. Summary with ASSUMPTIONS
  (source default/data) in offer_effectiveness.next_best_offer; offer facts
  (per offer rates, test p, never-offered churn, bias gap, customers and
  value per best offer) added to the results digest (Telco 11.2k tokens).
  Telco: 4,136 customers scored in 0.5 s; offer model CV ROC-AUC 0.48-0.64
  (weak signal); loyalty discount 1,793, 10GB booster 1,267, OTT 894,
  annual-plan month 128, no offer 54. Backend 255 (+ lift test).
- T5b.4: prompts/offer_message.v1.md + app/agents/offer_message.py: the fast
  model gets one customer's offer name and top 3 reasons only; every number
  in the message and SMS must come from the offer name, the name must appear
  unchanged, SMS <= 160; one retry with feedback, then a fixed template.
  Cached per customer and offer in the session folder (offer_messages.json).
  Endpoints: GET /predictions/{id}/offer/{customer} (all inputs, formula,
  assumptions), POST .../message (on demand). Contract types
  offer_effectiveness (offers, cells, tests, next_best_offer summary).
  UI: Risk Predictions "Next best offer" / "Expected value" columns; the
  offer opens a "Why this offer" panel (KaTeX formula with the customer's
  inputs, low-data flag, assumptions with source, Generate message);
  Recommendations "Offer performance" (accepted vs declined churn chart,
  cards with n and significance, warnings, next-best-offer summary, shown
  even when no AI recommendation passed); Data Health shows offer warnings.
  README limitations added. E2E covers the offer flow (template path).
  Live Gemini: 2 of 2 messages passed validation first try (SMS 146/145
  chars); prompt gained a rule against inventing customer history after
  one called a 4-month customer "long-standing". Backend 262, frontend 91.
- Phase 5b gate review: no High or Medium issues. Added a test for
  confirmed offer columns with every cell blank (no crash; everyone gets
  "No offer: no eligible offers"). Low items in Known issues. Backend 263,
  frontend 91, E2E 1 (offer flow included).
- T5c.1: app/stats/experiment_design.py (sample size per arm via statsmodels
  Cohen's h + NormalIndPower with ratio; absolute or relative MDE; smallest
  detectable effect for the available customers; duration from monthly
  volume; plain "Segment too small" warning with the detectable MDE; LaTeX
  formula). app/experiments/ (SQLAlchemy models Experiment + AuditLog,
  db.py SQLite/Postgres engine, lifecycle.py transitions that always audit),
  Alembic migration 0001 packaged under app/experiments/migrations and run by
  init_db(); the audit log is append-only in the ORM and via DB triggers
  (SQLite and Postgres). Backend 296 tests (33 new).
- T5c.2: /experiments API (create draft from a session + optional
  recommendation, list, get with audit trail, PATCH while draft, approve with
  approver + cost/eligibility checkbox, assign, assignment.csv).
  app/experiments/segments.py (flat AND filters, no eval),
  assignment.py (SHA-256 of "experiment_id:customer_id" -> [0,1) vs
  control_share; SMD balance check with |SMD| > 0.1 flags, per level for
  the plan column), data.py (session customers = cleaned data joined to
  predictions; covariates churn_probability, time_column, revenue_column
  and a plan/contract column found by name; attaches Phase 5b cached offer
  messages without generating new ones), service.py, migration 0002
  (experiment_assignments + design / assignment_summary / source_session_id).
  CORS now allows PATCH. Backend 317 (21 new), frontend unchanged (types
  regenerated).
- T5c.3: app/stats/experiment_analysis.py (SRM chi-square p < 0.001; ITT
  Wilson CIs, Newcombe hybrid-score CI of the difference, pooled z-test,
  achieved power for the design MDE at the observed n; business impact with
  CI and assumptions; per-protocol labelled biased; complaints / ARPU
  guardrails with Welch z CIs; pre-registered segments BH-corrected and
  labelled exploratory; decision helper ship / dont_ship / inconclusive
  (with extra sample) / untrustworthy). app/experiments/results.py validates
  the CSV against the assignment (unknown IDs, group mismatches, duplicates,
  0/1 fields, churn_date inside the window; early-look warning).
  POST /experiments/{id}/results (multipart + assumptions) and
  /experiments/{id}/analysis (recompute with new assumptions). Migration
  0003 (experiment_outcomes, preregistered_segments, analysis,
  segments per assignment). Backend 334 (17 new).
- T5c.4: prompts/experiment_summary.v1.md + app/experiments/summary.py
  (5 sentences; every figure checked against the analysis; may not go beyond
  the verdict; a negative figure may be written as its size; numbers in the
  offer name and the 95% level are allowed; retry, then template), cached per
  analysis. POST /experiments/{id}/decide (ship blocked on SRM; extend returns
  to running; ship / dont_ship write offer_evidence unless SRM failed). NBO
  uses the experiment's per-acceptor lift (ITT drop / acceptance rate) for
  proven offers and labels every offer experiment-proven or observational.
  Stateless POST /experiments/design (live wizard feedback), GET
  /experiments/segment-options/{session_id}, typed DesignOut / AnalysisOut
  contract, migration 0004. Frontend Experiments tab: list with status chips,
  design wizard (recommendation prefill, segment builder, MDE / power /
  split sliders with live sample size, pre-registered segments), approval,
  assignment with balance table and CSV link, results upload, results view
  (trust strip, per-arm bars with Wilson whiskers, forest plot, decision
  helper, validated summary, impact with editable assumptions recomputed on
  the server, guardrails, per-protocol caveat, decision form), audit trail;
  evidence badges on offer cards and the offer panel. AI requests get a
  150 s client timeout. Checked in a browser against a live backend: full
  lifecycle on Telco, live Gemini summary validated (source ai), and after
  "ship" a rerun labelled the offer experiment-proven. Backend 347,
  frontend 100.
- T5c.5: app/experiments/simulate.py + scripts/simulate_experiment.py
  (seed 42; real_effect 26% vs 21% with 45% acceptance, no_effect,
  broken_delivery 60/40 of a 50/50 plan; reads an assignment CSV or fetches
  it from the API). Tests: scenario 1 CI contains the true -5 points,
  scenario 2 is inconclusive or don't ship, scenario 3 is untrustworthy
  (SRM). POST /experiments/demo (sample data only, marked by meta.sample
  from POST /sample; ResultsResponse.sample tells the UI) creates a demo
  experiment with scenario 1 results; demo experiments (migration 0005)
  never block real ones and never write offer evidence. "Load demo
  experiment" button on the Experiments tab; the E2E walk-through now loads
  the demo, writes the (template) summary and records a decision.
  Backend 353, frontend 101, E2E 1.
- Phase 5c gate review. Fixed (High): experiments were global, so on a
  shared deployment anyone could list others' experiments and download their
  assignment CSVs (customer IDs, messages), and one user's decided experiment
  changed next best offer for everyone with the same offer name. Now every
  /experiments call needs an X-Workspace-Key (random per browser, only its
  SHA-256 is stored, migration 0006); other workspaces get 404, overlap and
  evidence are per workspace, uploads record the hash so offer_node reads
  only its own workspace's evidence; the CSV is fetched with the header.
  Fixed (Medium): the summary endpoint held a DB transaction open across the
  LLM call (now commits first and skips caching if the analysis changed);
  the async results upload ran parsing and statistics on the event loop
  (now a sync handler in the threadpool); a results file with only one arm
  gave a 500 (now 422). Low fixes: segment filter value lists capped at
  200; migrations read the dialect from the context so the Postgres SQL can
  be generated offline (checked: tables, ALTERs, trigger and function).
  Low, not fixed: see Known issues. Backend 359, frontend 103, E2E 1.
- T5d.1: app/stats/model_metrics.py (ROC-AUC, PR-AUC, precision/recall at
  top 10% with a stable tie order, decile lift and cumulative gains, Brier,
  10-bin calibration with counts, ROC and PR curves) on the Phase 4 test
  split; CalibratedClassifierCV fitted on the training split only (isotonic
  from 1,000 training rows). State key model_metrics_v2 (raw and
  calibrated). Predictions: churn_probability is now calibrated (risk bands,
  NBO and money metrics use it), churn_probability_raw keeps the model
  score, SHAP reasons still explain the raw model. Telco: Brier 0.168 ->
  0.140, ROC-AUC 0.829 unchanged, top-10% precision 70.7%; High band 2,239
  -> 667 customers. Backend 369 (10 new).
- T5d.2: app/config.py became the package app/config/ (same imports) holding
  offers.yaml (5 offers named like the sample data's offers) and pricing.yaml
  (free tier, 0); app/catalog.py validates both (errors name the YAML
  line). app/stats/business_metrics.py: revenue at risk, expected saving
  (per_accepted / per_targeted), eligibility rules (missing column -> offer
  skipped with a warning), next best offer ("No offer" when <= 0), ROI by
  segment, data overrides (Phase 5b rates, Phase 5c evidence preferred) and
  an ASSUMPTIONS block with sources. app/business.py computes it per session
  (disabled with a reason without an ARPU column; user edits > data >
  YAML). Backend 388 (19 new).
- T5d.3: experiment_design.sample_size_two_proportions (relative lift,
  two-sided, ratio; returns p1, p2, Cohen's h, z values, n per arm, total,
  LaTeX); references 903 (p1 0.20, lift 0.25; statsmodels 902.34) and 1038
  (p1 0.26, lift 0.20) per arm. business_metrics.ab_plan sizes a test for
  the customers who get an offer (p1 = their observed churn), warns when
  they are too few, with an ASSUMPTIONS block. Backend 397 (9 new).
- T5d.4: app/graph/telemetry.py: traced() wraps every node (outside
  safe_node, so failed runs are timed) and appends {node, started_at,
  latency_ms, status, retries, llm_calls, input/output tokens, model} to
  telemetry_events; tokens are tied to the node run through a context
  variable fed by the llm usage listener (correct under the parallel
  fan-out; no prompt text). summarise_run: validator counts and figures
  caught, retries, schema corrections, latency per node / total / wall
  clock, tokens per model, ESTIMATED cost from pricing.yaml. Summaries are
  saved to the runs table (migration 0007) when a run finishes, scoped by
  the session's workspace. Backend 406 (6 new).
- T5d.5: GET /metrics/model/{id}, GET and POST /metrics/business/{id}
  (validated assumptions: months 1-60, per-offer acceptance / save rate /
  cost, relative lift 0.01-0.9, alpha, power; recompute 0.02 s on Telco),
  POST /metrics/business/{id}/explain (prompts/business_explanation.v1.md,
  3 validated sentences, cached per assumptions hash, template fallback),
  GET /telemetry/{id} (live summary) and GET /telemetry/runs (per
  workspace). Typed contract in app/api/metrics_contract.py. Upload 422s:
  a churn-named column with one value, and no two-value column at all (SPEC
  message); fewer than MIN_ROWS rows already existed. Backend 425.
- T5d.6: one PlotlyChart wrapper (components/charts; next/dynamic ssr:false,
  the 1.1 MB plotly.js-basic-dist-min chunk loads only when a chart
  mounts; theme follows the colour scheme). New tabs: Model Performance
  (KPI tiles with keyboard/touch help, ROC, PR, lift + cumulative gains,
  calibration raw vs calibrated, plus the metrics table and confusion
  matrix moved from Churn Drivers; the Recharts ROC chart was removed),
  Business Impact (assumptions panel posting to the API debounced 400 ms,
  KPIs, ROI by segment, top-50 next best offers, A/B plan with KaTeX,
  every assumption labelled with its source, explanation card with
  "Based on default assumptions" + "Regenerate explanation" when the
  numbers changed), Agent Health (validator pass rate from the API,
  figures caught, schema corrections, run time, tokens, ESTIMATED cost,
  time per step, retries, trend of recent runs). Checked at 375 px (no
  page scroll); fixes from that check: bar labels hover-only, and the plan
  column now prefers Contract over CityTier (hint priority). E2E opens the
  three tabs and edits months remaining. Backend 425, frontend 113, E2E 1.
- Phase 5d gate review. Fixed (Medium): run time included the wait for the
  human to confirm the schema (now busy time = union of step intervals);
  numeric offer rules compared as text (YAML 1 never matched 1.0). No High
  issues. Low, not fixed: see Known issues. Backend 427, frontend 113, E2E 1.
- T7.1: Ask the Data. app/chat/tools.py (get_stat over whitelisted result
  roots, get_segment, get_test_result, get_customer_risk (score, band and
  reasons only), filter_and_aggregate with Pydantic-validated args: known
  non-ID columns, ops == != > >= < <= in, metrics count/mean/median/sum/
  churn_rate, max 3 filters, 50 rows; plain pandas, no eval/query).
  app/chat/agent.py: LangGraph loop agent -> tools -> agent; each LLM step
  is a structured ChatStep (call_tool / answer / refuse) via the wrapper;
  max 6 tool calls; answer numbers must appear in this question's tool
  results (one retry, then withheld). prompts/chat_agent.v1.md. History:
  last 10 messages in the session folder. POST /chat/{id} (per-IP sliding
  window, CHAT_PER_MINUTE=10; X-Forwarded-For only with TRUST_PROXY_HEADERS)
  and GET /chat/{id}. Ask the Data tab with example questions, loading
  state and the tools used under each answer. Backend 451, frontend 117.
- T7.2: exports on demand. app/exports/excel.py (openpyxl: Cleaned_Data,
  Predictions, Hypothesis_Tests, Drivers, Recommendations; bold header,
  frozen panes, one Excel table per sheet, number formats, no merged cells,
  formula-looking text written as text), app/exports/pdf.py (reportlab:
  cover, executive summary, 3 matplotlib charts, insights,
  recommendations, methodology, limitations, validator summary; 5 pages on
  Telco), report_node marks exports ready, GET /export/{id}/excel and /pdf
  build once per analysis checkpoint and cache in the session folder.
  Telco: Excel 2.4 s / 1.7 MB, PDF 0.4 s. Download links in the dashboard
  header; E2E fetches both. Backend 457, frontend 115, E2E 1.
- Phase 7 gate review. Fixed (Medium): a chat question had no overall time
  limit (8 LLM steps x 45 s timeouts x retries); now 120 s per question,
  status "timeout". Fixed (Low): the rate limiter pruned no idle IPs. Low,
  not fixed: see Known issues. Backend 459, frontend 115, E2E 1.
- T8.1: render.yaml (one Docker web service, healthCheckPath /health,
  secrets sync: false), multi-stage Dockerfile (deps in a venv, slim
  runtime, non-root uid 1000, uvicorn --workers 1 --proxy-headers, PORT
  from env), CORS FRONTEND_ORIGIN + FRONTEND_ORIGIN_REGEX (Vercel
  previews), JSON logs with session_id (request middleware + run threads;
  root logger and warnings too), per-IP limits on /upload and /sample
  (UPLOAD_PER_MINUTE) and every AI endpoint (AI_PER_MINUTE; chat has
  CHAT_PER_MINUTE), frontend "Waking up the server (up to a minute)..."
  with retries for 90 s. Added langgraph-checkpoint-postgres 3.1.2 so
  DATABASE_URL works for the checkpointer too. Docker checked (approved by
  the human): image builds (1.74 GB), runs as uid 1000; the full Telco flow
  against it with real Gemini finished in 132 s (6 insights and 5
  recommendations; validator 11/15, 4 dropped), plus model and business
  metrics, telemetry, both exports and a chat answer; logs were JSON with
  session_id and no key. Backend 465, frontend 117, E2E 1.

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
- Gemini models now (T5.5): GEMINI_MODEL = GEMINI_MODEL_FAST =
  gemini-3.1-flash-lite, GEMINI_MODEL_FALLBACK = gemini-3.8-flash,
  GEMINI_RPM = 5. Reason: the free tier allows only 20 requests/day on
  gemini-3.8-flash, which tests and runs exhausted; flash-lite answered
  reliably in ~5 s. Change backend/.env if you enable billing.
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
- Dev dependencies added in T6.1 (frontend): openapi-typescript (types from
  OpenAPI), vitest + @testing-library/react + jsdom (hook tests, required by
  the runbook). @types/node raised to ^24 to match Node 24 (vitest's peer range).
- recharts 3 added in T6.2 (listed in the CLAUDE.md stack) for dashboard charts.
- Results sub-objects are still dict[str, Any] in the contract; each T6.3 tab
  adds typed models for the keys it reads.
- T5b.2: offer leakage and selection-bias warnings live in
  offer_effectiveness.warnings, not data_health (runbook wording): data_health
  has one producer (cleaning), and the bias check needs Phase 4 risk scores.
  T5b.4 shows them on the Data Health tab and the offer cards. Offer tests run
  in the hypothesis step so there is one BH family; leakage-dropped offers
  count their customers as never offered (not offered at observation time).
- T5b.3 deviations from the runbook: (1) P(accept) models are unweighted
  logistic regressions, not class_weight="balanced": the expected value is a
  money metric and needs calibrated probabilities (CLAUDE.md rule 23);
  balancing inflates them. (2) Cost is subtracted as P(accept) x cost per
  acceptance: OfferCost is only paid when an offer is accepted (0
  otherwise). (2b) The value uses retention_lift = max(0, P(stay | accepted) -
  P(stay | declined)) instead of P(stay | accepted): the runbook's version
  credits every acceptor who would have stayed anyway, so on Telco it
  recommended the device upgrade credit (no churn effect per the data
  dictionary) to 371 customers and summed to 1.04M expected value; with the
  lift it recommends only offers that retain more acceptors than decliners
  (loyalty discount leads, 54 customers get "No offer", total 187K). Both
  probabilities and the lift are stored per customer. (3) Next-best-offer rows go to their own
  next_best_offers.parquet (state key offer_recommendations_path, SPEC)
  rather than predictions.parquet, which belongs to modelling_node; the API
  joins them. (4) The discount rule reads "NN% discount/off" from the offer
  name; offers without one are eligible. (5) A decline with an unknown date
  counts as recent. P(churn) is still the uncalibrated churn score until
  Phase 5d.
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
- T5c.1 dependencies: sqlalchemy 2.1.1 + alembic 1.20.0 (the v1.2 spec
  requires SQLAlchemy + Alembic for experiments) and psycopg[binary] 3.3.2
  (driver so DATABASE_URL=postgres... works; postgres:// URLs are rewritten
  to postgresql+psycopg://).
- T5c.1: MDE accepts mde_type absolute (runbook T5c.1, default) or relative
  (v1.3 spec for the 5d A/B plan), one shared function. The treatment is
  expected to lower churn (p2 = p1 - mde); the test is still two-sided.
  Experiment stores n_required_treatment and n_required_control instead of a
  single n_required_per_arm (unequal splits need different sizes), plus
  outcome_window_days for "churn within N days". Power must be in [0.5, 1),
  control share in [0.05, 0.95].
- T5c.2: an experiment's baseline is the segment's measured churn rate
  unless the user enters one (assumption source data | user; alpha, power
  and control share default | user). Assignment may use a newer analysed
  session than the design (sessions expire after 2 h); the session used is
  in the audit row. Customers in experiments with status running or
  results_uploaded are excluded from new assignments. Assignment keeps
  under-powered or imbalanced groups but records warnings (the hash is
  deterministic, so re-randomising is not possible without a new experiment).
- T5c.3: assigned customers missing from the results file are a warning
  (with counts per arm), not an error: lost customers are what the SRM
  check exists to catch, so rejecting them would hide a broken delivery.
  Unknown IDs, group mismatches and duplicates are rejected (422). ITT then
  covers the customers with outcomes. Guardrails are breached only when the
  95% CI shows the bad direction beyond a tolerance (complaints 0, ARPU 5%
  of the control mean, editable): a discount lowers ARPU by design. Customer
  value defaults to the assigned customers' mean monthly revenue x
  NBO_HORIZON_MONTHS (source data); offer cost has no default, and without
  it the decision helper cannot say "ship". Pre-registered segments are
  fixed in the draft and membership is stored at assignment, because the
  session data expires before results arrive. SRM failure gives the verdict
  "untrustworthy" (blocks ship).
- T5d.2: PyYAML pinned (6.0.3, already installed via langchain-core; now
  imported directly for offers.yaml / pricing.yaml). Business metrics are
  computed on request (not stored in graph state): data overrides need
  offer_node's output and assumption edits recompute anyway. Data save
  rates: experiment = retention lift per acceptor / control churn;
  observational = (churn if declined - churn if accepted) / churn if
  declined. ROI = net expected saving / expected offer cost.
- T5d.4: schema corrections are computed from state (schema_proposal vs
  confirmed_schema) in the run summary rather than inside /confirm-schema:
  same inputs, one place, and nothing extra to store.
- T5d.6 dependency: plotly.js-basic-dist-min 4.1.1 (SPEC v1.3), used
  directly through a 20-line wrapper instead of react-plotly.js (whose peer
  is the full plotly.js). Explanations of business metrics are written on
  demand (button), not on page load, to save free-tier calls.
- T7.1: the chat agent is a hand-built LangGraph ReAct loop with structured
  steps instead of native tool calling, so it keeps CLAUDE.md rules 5 and 19
  (Pydantic structured output, flat schemas) and the number check of rule 4.
- T7.2 dependencies: reportlab 5.0.1 (PDF; chosen over WeasyPrint because it
  needs no Pango/Cairo system packages in Docker) and matplotlib 3.11.2
  (already installed via SHAP; pinned because the PDF charts import it).
- T7.1 live check (real Gemini, 5 calls, 4,105 in / 288 out tokens): the
  agent answered "month-to-month, tenure <= 12" churn (44.33%, from
  filter_and_aggregate) and the PaymentMethod test (from get_test_result)
  correctly with the tool cited, and refused a prompt-injection attempt
  without calling any tool.

## Checkpoints for the human
- S8 (T5d.0): Phase 5d plan written above under "Phase 5d plan" (FULL-AUTO:
  recorded as a checkpoint, work continued). Deviations to note: app/config.py
  becomes a package so offers.yaml / pricing.yaml can live in app/config/;
  no react-plotly.js (full plotly.js peer); calibrated probabilities replace
  raw ones for risk bands, NBO and money metrics.
- S6 (end of Phase 6, MVP): run the app locally and click through all tabs:
  backend `cd backend && .venv/bin/uvicorn app.main:app --port 8010`,
  frontend `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8010 npm run dev`,
  open http://localhost:3000 and press "Try sample data". Or run
  `cd frontend && npm run e2e` for the automated walk-through.
- S1 (T1.1): architecture summary, graph flow and risks are under Decisions above.
- S5 (T5.5): live Telco run with real Gemini, see docs/runs/phase5_telco_run.md
  (11/15 AI items verified by the validator; top insight: Month-to-month
  contracts churn at 39.81% vs 25.66% overall; top recommendation: move
  monthly customers to annual contracts).
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
- (Resolved in T5b.1) Campaign/offer columns are now excluded from
  segmentation, hypothesis tests and the model once confirmed.
- (Resolved in T5d.1) Risk bands, NBO and money metrics now use calibrated
  probabilities (Telco High band: 2,239 -> 667 customers).
- Hypothesis test cap (40) keeps columns in data order; with more candidates
  the last ones are skipped (Telco no longer hits it: 35 tests after T5b.1).
- Prompt injection: column names and category values from the uploaded file
  appear in LLM prompts. Every number is still validated against state, so
  the risk is misleading wording, not wrong numbers. Consider sanitising
  labels (Phase 8 hardening).
- At temperature 0, flash-lite often repeats the same unlisted numbers on a
  retry despite feedback; those items are then dropped (by design).
- Per-IP rate limiting on /upload and /chat (SPEC API section) is not built
  yet; planned for Phase 8 hardening.

- Phase 6 (Low): the 30 s client timeout can be short for a 10 MB upload on a
  slow connection; /results sends the whole state on every call (~300 KB on
  Telco); /predictions is not rate-limited yet (Phase 8 hardening).

- Phase 5b (Low): the offer-message endpoint can be called for many
  customers (each first call is one LLM call; bounded by GEMINI_RPM and the
  cache, per-IP limits come in Phase 8); offer names and reasons from the
  uploaded file reach the message prompt (numbers are validated, wording is
  not); duplicate customer IDs would share one row's features in next-best-
  offer scoring; offer acceptance models are weak on Telco (CV ROC-AUC
  0.48-0.64), so offer choice leans on the retention lift.
- Phase 5c (Low, T5c.2): two experiments assigned at the same moment could
  both claim the same customers (no DB lock across the overlap check);
  assignment.csv does not neutralise spreadsheet formulas in messages.
- Phase 5c (Low, gate): Postgres was checked with offline SQL only (no
  local Postgres; Docker needs the human's OK), and the Docker image was not
  rebuilt for the new dependencies (sqlalchemy, alembic, psycopg[binary];
  migrations ship inside the app package). The workspace key is a bearer
  key in localStorage, not a login: clearing browser storage loses access to
  that browser's experiments. Restarting the API re-runs an analysis when
  the dashboard reloads (existing RunManager behaviour, seen during the
  T5c.4 browser check). OfferEvidence.decided_at comes back without a
  timezone on SQLite.
- Phase 5d (Low, gate): POST /metrics/business/{id}/explain costs one LLM
  call per new set of assumptions (cached per set; per-IP limits come in
  Phase 8). Calibration adds 5 cross-validated fits of the chosen model to
  training time. Calibrated risk bands score fewer customers for next best
  offer on Telco (2,622 Medium+High vs 4,136 before), as intended.
- Phase 7 (Low, gate): get_customer_risk passes one customer's SHAP reason
  strings (feature: value) to the LLM when the user asks about that customer
  (the spec requires the tool; no other row data reaches the model). Excel
  export of a 100k-row file will be slow (openpyxl, tables need the normal
  writer); consider xlsxwriter if that matters. The export build lock is
  global (one export at a time). Docker image not rebuilt for reportlab /
  matplotlib (pure wheels; no system packages needed).

## Human actions needed
- S7 at the end: Render + Vercel dashboard steps (paste GEMINI_API_KEY into Render yourself).
