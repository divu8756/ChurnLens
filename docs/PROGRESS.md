# ChurnLens progress

Project root: /Users/divyanshusrivastava/ChurnLens

## Current task
Phase 5b gate (review, PR)

## Next step
Phase 5b gate: strict review of git diff main...phase-5b, fix High/Medium,
push, open the PR; the human merges it. Then Phase 5c (A/B testing).

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

## Checkpoints for the human
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
- Risk bands use the chosen model's raw probabilities. With class_weight=
  "balanced" these run high (Telco: 32% High vs ~25% churn). Phase 5d adds
  calibration (CalibratedClassifierCV on train); switch bands and money
  metrics to calibrated probabilities there.
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

## Human actions needed
- S7 at the end: Render + Vercel dashboard steps (paste GEMINI_API_KEY into Render yourself).
