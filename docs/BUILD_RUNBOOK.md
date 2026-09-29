# ChurnLens: Build Runbook for Claude Code (v1.4, autopilot)

Version 1.4 · Gemini API · metrics layer · FULL-AUTO autopilot (see CLAUDE.md) · LangGraph · FastAPI on Render · Next.js on Vercel

This single file is the complete build plan. Claude Code reads it and builds ChurnLens task by task, testing and committing as it goes, and stops only where a human decision or credential is needed.

## 1. For the human: how to run this

### Before you start (one time)

- Install: Homebrew, then `brew install python@3.11 node git gh libomp pandoc`, and Claude Code (`npm install -g @anthropic-ai/claude-code`).
- Accounts: GitHub (`gh auth login`), Vercel and Render (sign up with GitHub), Google AI Studio (create a Gemini API key; note the current Pro and Flash model names).
- Create the project folder: `mkdir churnlens && cd churnlens && git init && mkdir -p docs backend/sample_data`.
- Sample data is generated automatically by scripts/generate_telco_sample.py (IBM-Telco-style, 7,000 customers + retention offers, fixed seed) and scripts/generate_india_sample.py (4-table India dataset). No download needed.
- Put this runbook in the repo as Markdown: `docs/BUILD_RUNBOOK.md`. If you only have the Word version, convert it: `pandoc ChurnLens_Build_Runbook.docx -t gfm -o docs/BUILD_RUNBOOK.md`. Claude Code reads Markdown natively; it cannot reliably read .docx.
- Start Claude Code in the folder: `claude`.

### Kickoff prompt (paste this into Claude Code)

```text
Read docs/BUILD_RUNBOOK.md completely before doing anything. It is
your build plan for ChurnLens. Follow its Execution Protocol (section 2)
exactly, in AUTONOMOUS mode. Execute the tasks in section 4 in the
order listed, starting with Task T1.1. Stop only at HUMAN STOP points
or when the protocol tells you to stop.
```

### Resume prompt (after a break, a /clear, or a new session)

```text
Read CLAUDE.md, docs/BUILD_RUNBOOK.md and docs/PROGRESS.md. Continue
from the "Current task" in PROGRESS.md, following the Execution Protocol
in AUTONOMOUS mode. First run all tests to confirm the repo is green;
if not, fix that before continuing.
```

### Want more control? Use STEP mode

Replace AUTONOMOUS with STEP in the kickoff prompt. Claude Code will then stop after every task and wait for you to type `continue`. Use STEP mode for Phases 2 and 3 if you want to learn the code as it is written.

### What you will be asked to do (the HUMAN STOP points)

| Stop | When | What you do |
| --- | --- | --- |
| S1 | After T1.1 | Read the architecture summary in docs/PROGRESS.md. Reply `continue` or give corrections. |
| S2 | During T1.2 | Fill `backend/.env` with your Gemini key and model names (copy from `.env.example`). Reply `continue`. |
| S3 | T1.3 | Make sure `gh auth status` shows you are logged in. Reply `continue`. |
| S4 | End of T1.4 | Allow one real Gemini smoke-test call (costs nothing on the free tier). Reply `run it` or `skip`. |
| S5 | End of Phase 5 | Allow one full Telco run with real Gemini calls and review the insights and the token log. Reply `continue`. |
| S6 | End of Phase 6 (MVP) | Open the app locally, click through all tabs. Reply `continue` for 5b/5c, or `deploy` to jump to Phase 8 first. |
| S8 | T5d.0 (metrics layer) | Read the Phase 5d plan in docs/PROGRESS.md. Reply `go` or give corrections. |
| S7 | Phase 8 | Do the Render and Vercel dashboard steps listed in T8.2. Paste both URLs back. Claude Code finishes the wiring. |

Claude Code will also stop and ask you whenever a gate fails twice, the spec is ambiguous in a way that changes behaviour, a new paid service or secret is needed, or a destructive git action would be required.

## 2. Execution Protocol (for Claude Code)

Claude Code: these rules govern how you run every task in this file. CLAUDE.md (Appendix A) governs how you write code. docs/SPEC.md (Appendix B) governs what you build.

```text
EXECUTION PROTOCOL

Modes
- AUTONOMOUS: run tasks back to back. Stop only at HUMAN STOP points or
  on a stop condition below.
- STEP: stop after every task, show a short summary, and wait for the
  human to type "continue".

Before the first task
1. Confirm the repo root contains docs/BUILD_RUNBOOK.md and
   backend/sample_data/telco_churn.csv. If the CSV is missing, generate
   it: python3 scripts/generate_telco_sample.py backend/sample_data/telco_churn.csv
2. Check tool versions: python3.11, node >= 20, git, gh. Report any gap.

Standard Task Protocol (run for EVERY task)
1. Set "Current task" in docs/PROGRESS.md to the task ID.
2. Plan: list files to create or change, approach in short steps, edge
   cases, and the tests you will write. Write this plan into
   PROGRESS.md under the task. (In STEP mode, show it and wait.)
3. Write the tests first for core logic, then the implementation.
4. Run the task's tests, then the full suite, lint and typecheck:
   backend: ruff check . && pytest -q
   frontend (once it has code): npm run lint && npm run typecheck && npm run build
   Show the real output. Never claim a result you did not run.
5. If anything fails: find the root cause and fix it. Do not skip tests,
   loosen assertions, add "# type: ignore", use `any`, or swallow
   exceptions. After 2 failed fix attempts on the same problem, STOP and
   report: the error, what you tried, and 2 hypotheses.
6. Check every "Tests:" and "Done when:" item in the task is satisfied.
7. Record in PROGRESS.md under Done: task ID, one-line summary, test
   counts, and anything still risky.
8. Commit on the current phase branch with a conventional-commit message.

End of every phase (Phase Gate)
1. Act as a strict senior reviewer who did not write this code. Review
   `git diff main...HEAD` for: bugs, unhandled errors, edge cases (empty
   file, 1 column, all-null column, single-class target, non-English
   headers, 100k rows), security (secrets, upload validation, injection),
   hard-coded values, missing tests, and CLAUDE.md violations.
2. List issues by severity. Fix all High and Medium. Re-run everything.
3. Push the branch, open a PR with gh, wait for CI. If CI fails, fix it.
   When CI is green, merge to main (squash) and delete the branch.
4. Update PROGRESS.md (Done, Decisions, Known issues) and set Current
   task to the first task of the next phase.
5. Tell the human: "Phase N complete." In AUTONOMOUS mode continue to
   the next phase; if your context is getting long, suggest the human
   run /clear and send the Resume prompt.

Branches
- One branch per phase: phase-1, phase-2, ..., phase-5b, phase-5c, phase-5d.
- Never force-push main. Never rewrite published history.

Stop conditions (always stop and ask the human)
- A HUMAN STOP point.
- The same failure survives 2 fix attempts.
- The spec is ambiguous in a way that changes user-visible behaviour.
- A secret, paid service, or account action is needed.
- A destructive action (deleting data, resetting git, dropping tables).
- A task would require changing a locked decision in SPEC or CLAUDE.md.

Never
- Put secrets in code, logs, commits or PROGRESS.md.
- Call the real Gemini API from tests or CI.
- Mark a task done without running its tests.
- Build later tasks early "to save time".
```

## 3. Execution order at a glance

| Order | Phase | What it delivers |
| --- | --- | --- |
| 1 | Phase 1 | Scaffold, CI, Gemini wrapper |
| 2 | Phase 2 | State, ingest, schema agent, human-in-the-loop, cleaning |
| 3 | Phase 3 | EDA, segmentation, survival, hypothesis tests |
| 4 | Phase 4 | Model, SHAP, odds ratios, predictions |
| 5 | Phase 5 | Impact, insight, recommendation, validator agents |
| 6 | Phase 6 | Dashboard + live progress (MVP complete) |
| 7 | Phase 5b | Next best offer |
| 8 | Phase 5c | A/B testing + Experiments tab |
| 9 | Phase 5d | Metrics layer: model, business, telemetry + 3 tabs |
| 10 | Phase 7 | Chat agent + exports |
| 11 | Phase 8 | Production hardening, deploy, README |

Phases 5b and 5c run after Phase 6 because they add UI to the dashboard that Phase 6 creates.

## 4. Tasks

## Phase 1: Scaffold, CI, Gemini wrapper

### Task T1.1: Save the rulebook and restate the plan

```text
Create CLAUDE.md with exactly the content of Appendix A of
docs/BUILD_RUNBOOK.md. Create docs/SPEC.md with exactly the content of
Appendix B. Create docs/PROGRESS.md with sections: Current task, Done,
Decisions, Known issues, Human actions needed.
Then read all three and write, into PROGRESS.md under Decisions: the
architecture restated in 10 lines, the LangGraph flow as a Mermaid
diagram, and your top 5 risks with mitigations. Do not write any
application code in this task.
```

**HUMAN STOP S1: human reviews the architecture summary.**

### Task T1.2: Build the skeleton

```text
Phase 1 of docs/SPEC.md: scaffold only, no business logic.

backend/
- Python 3.11 venv at backend/.venv; pyproject.toml with pinned
versions; ruff + pytest configured.
- app/main.py: FastAPI with GET /health returning {status, version},
CORS limited to FRONTEND_ORIGIN from env.
- app/config.py: pydantic-settings reading GEMINI_API_KEY,
GEMINI_MODEL, GEMINI_MODEL_FAST, GEMINI_RPM, FRONTEND_ORIGIN, DATA_DIR,
DATABASE_URL (optional), MAX_UPLOAD_MB=10, MAX_ROWS=100000.
Fail fast with a clear message if a required var is missing.
- Empty packages: app/agents, app/graph, app/prompts, app/stats,
app/api, tests/. Keep backend/sample_data/telco_churn.csv (already present).
- Dockerfile (python:3.11-slim, non-root user, uvicorn on $PORT).
- tests/test_health.py.

frontend/
- Next.js App Router, TypeScript strict, Tailwind, ESLint.
- Scripts: lint, typecheck (tsc --noEmit), build.
- lib/api.ts reading NEXT_PUBLIC_API_URL; a home page that calls
/health and shows "Backend: online/offline".

root
- .gitignore (.env*, !.env.example, .venv, node_modules, .next,
data/, *.db, __pycache__), MIT LICENSE, README placeholder.
- backend/.env.example and frontend/.env.example (names, no values).
  Then copy them to backend/.env and frontend/.env.local and STOP (S2)
  asking the human to fill the values before anything reads them.
- .github/workflows/ci.yml: on push + PR; backend job (ruff, pytest)
and frontend job (npm ci, lint, typecheck, build). Cache deps.

Done when: health test passes, frontend builds, the home page shows
"online" with both running locally, and CI is green on GitHub.
Apply the Standard Task Protocol (section 2).
```

**HUMAN STOP S2: human fills backend/.env.**

### Task T1.3: Create the GitHub repo

```text
Create a public GitHub repo "churnlens" with gh, push main, and
show me the CI run result. Confirm no .env file is tracked.
If `gh auth status` fails, STOP (S3) and ask the human to log in.
```

**HUMAN STOP S3 only if gh is not authenticated.**

### Task T1.4: The Gemini wrapper

```text
Create backend/app/llm.py, the only place that talks to Gemini
(CLAUDE.md rules 16-20). Use ChatGoogleGenerativeAI from
langchain-google-genai with the key from settings.GEMINI_API_KEY.
Expose:
- get_llm(tier: "pro" | "fast", temperature: float) -> model
(pro = GEMINI_MODEL, fast = GEMINI_MODEL_FAST)
- structured_call(tier, temperature, prompt, schema: type[BaseModel],
timeout_s=60) -> schema instance, using with_structured_output.
Behaviour:
- Token-bucket throttle at GEMINI_RPM (default 10) shared across the
process, including parallel graph nodes.
- Retry with exponential backoff + jitter on 429/RESOURCE_EXHAUSTED,
500, 503 and timeouts: max 3 attempts, and honour any retry delay
the API returns.
- Treat blocked or empty responses and Pydantic validation errors as
failures: 1 retry, then raise LLMUnavailable so the node's fallback
runs.
- Log model, tier, latency, input/output tokens (from usage metadata)
and outcome per call; never log prompt contents.
- A FakeLLM for tests that returns fixtures by schema name.
Add scripts/gemini_smoke_test.py: one real call with a tiny schema,
run manually, never in CI.
Tests: throttle spaces calls correctly; 429 then success retries and
succeeds; a blocked response raises LLMUnavailable after 1 retry;
invalid JSON is retried; tier maps to the right env model.
Apply the Standard Task Protocol (section 2).
At the end, STOP (S4) and ask the human before running the real
smoke test.
```

**HUMAN STOP S4: human approves one real Gemini call.**

Then run the Phase Gate.

## Phase 2: State, ingest, schema agent, human-in-the-loop, cleaning

### Task T2.1: State + graph skeleton with stubs

```text
Phase 2, step 1. Implement the full State model from docs/SPEC.md
in backend/app/graph/state.py (errors and progress use
Annotated[list, operator.add]). Build backend/app/graph/builder.py
with ALL nodes and edges from SPEC as stubs that only append to
progress, including the parallel fan-out, the conditional edge
to survival, the validator loop, and error_node.
Checkpointer: SqliteSaver at DATA_DIR/checkpoints.db, or PostgresSaver
when DATABASE_URL is set, behind one factory function.
Tests: the stub graph runs start to END; fan-out nodes all run and
their progress entries merge without errors; survival is skipped when
time_column is None; a fatal error routes to error_node.
Also export the graph as a Mermaid PNG/text to docs/graph.md.
Apply the Standard Task Protocol (section 2).
```

### Task T2.2: Upload + ingest

```text
Phase 2, step 2. Implement POST /upload and POST /sample, and
ingest_node, per SPEC upload rules. Validate extension AND actual
content (not just the filename), size, and row limits. For .xlsx,
return the sheet list and accept a sheet choice. Save as parquet under
DATA_DIR/{session_id}. Add a background cleanup that deletes sessions
older than 2 hours. Return clear 4xx messages for each failure.
Tests: valid CSV, valid multi-sheet xlsx, wrong extension, renamed
binary file, empty file, header-only file, 99 rows (reject), file over
the size limit, non-UTF-8 CSV (latin-1), and duplicate column names.
Apply the Standard Task Protocol (section 2).
```

### Task T2.3: Schema agent + its prompt file

```text
Phase 2, step 3. Create backend/app/prompts/schema_agent.v1.md
(role, task, input schema, output schema, rules, 2 few-shot examples:
one Telco-like, one where the target is called "Exited" with 0/1).
Implement schema_agent with with_structured_output and a Pydantic
SchemaProposal: columns[{name, semantic_type: id|numeric|
categorical|binary|datetime|text, confidence}], target_column,
positive_label, id_columns, time_column, reasoning.
The LLM receives ONLY: names, dtypes, 5 sample values, null %,
unique count. Add a deterministic pre-check in Python that flags
likely IDs (unique ratio > 0.95) and likely targets (names containing
churn/exited/attrition/left, binary). Merge: Python heuristics win on
IDs; the LLM proposes the rest. Temperature 0, timeout 30 s, 2 retries,
and a fallback to heuristics-only if the LLM fails.
Tests (mock the LLM, no real API calls in CI): prompt payload contains
no raw rows beyond 5 samples; fallback works; a malformed LLM output
is rejected by Pydantic.
Apply the Standard Task Protocol (section 2).
```

### Task T2.4: Human-in-the-loop interrupt + progress stream

```text
Phase 2, step 4. Implement human_review as its own node that ONLY
calls interrupt() with the SchemaProposal (no LLM call or side effect
before interrupt, because the node re-runs on resume). Implement
POST /confirm-schema/{id}: validate the confirmed schema (target
exists, is binary or mappable to binary, positive_label present,
id columns exist), then resume with Command(resume=...) using
thread_id=session_id.
Run the graph in a background task. Implement GET /stream/{id} as
SSE: node start/finish events, an "awaiting_confirmation" event with
the proposal, errors, a 15 s heartbeat, and a final "done" event.
Unknown or expired session returns 410.
Tests: graph pauses at human_review; resume with a valid schema
continues to cleaning; an invalid schema returns 422 and stays paused;
resuming twice is rejected; SSE emits events in the right order.
Apply the Standard Task Protocol (section 2).
```

### Task T2.5: Cleaning node + data health

```text
Phase 2, step 5. Implement cleaning_node per SPEC as pure functions in
backend/app/stats/cleaning.py, called by the node. Handle: blank
strings to NaN and numeric coercion (Telco TotalCharges), trimming
whitespace and unifying case in categoricals, duplicates, missing
values, target mapped to 0/1 using positive_label, IQR + z-score
outlier flags (flag, don't delete). Every action appends
{step, column, rows_affected, detail} to cleaning_log. Compute
data_health: rows before/after, % missing per column, duplicates
removed, outliers flagged, class balance, and a 0-100 health score
with its formula documented.
Fatal: single-class target or < 100 rows after cleaning, routed to
error_node.
Tests on small hand-made dataframes for each rule, plus the Telco file:
TotalCharges becomes numeric with exactly 11 blanks handled.
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 3: EDA, segmentation, survival, hypothesis tests

Pattern for every node here: maths in backend/app/stats/*.py as pure functions (dataframe in, dict out); the node file is a thin wrapper that reads state, calls the functions and writes only its own keys.

### Task T3.1: EDA node

```text
Phase 3, step 1. Implement eda_node per SPEC with pure functions in
stats/eda.py. Output must be JSON-serialisable (no numpy types, NaN
becomes null). For churn rate by category include n per level and
sort by churn rate. Correlation matrix on numerics only. Tenure bands
only if time_column exists. Cap categorical levels shown at 20
(rest = "Other").
Tests: a hand-made dataframe where the churn rates are known exactly;
all-null column; a single numeric column; output passes json.dumps.
Apply the Standard Task Protocol (section 2).
```

### Task T3.2: Segmentation node

```text
Phase 3, step 2. Implement segmentation_node: select numeric features
(exclude id, target, and time columns), impute + standard-scale,
K-means for k=2..8 with n_init=10 and random_state=42, pick k by
silhouette (sample 5,000 rows if larger). Profile each segment: size,
% of base, churn rate, mean of each feature vs overall, and an
auto-label from its top 2 distinguishing features (e.g. "High charges,
short tenure"). Skip gracefully if fewer than 2 numeric features.
Tests: 3 obvious synthetic blobs give k=3; results are reproducible
across runs; skip path works.
Apply the Standard Task Protocol (section 2).
```

### Task T3.3: Survival node

```text
Phase 3, step 3. Implement survival_node with lifelines:
Kaplan-Meier overall and for the top 3 categoricals by chi-square
strength (max 6 levels each), median survival time (or "not reached"),
survival at 6/12/24 time units, and log-rank test p-values. Downsample
curve points to <= 200 per line for the UI. Runs only when
time_column exists.
Tests: compare one KM curve and one log-rank p-value to lifelines
called directly; the "median not reached" case.
Apply the Standard Task Protocol (section 2).
```

### Task T3.4: Hypothesis testing node

```text
Phase 3, step 4. Implement hypothesis_node exactly per SPEC in
stats/hypothesis.py. For every test store: test_name, variable,
H0, H1 (plain English), assumption checks with results, the chosen
test and why, inputs (observed/expected tables or group
means/medians/SDs/n), each calculation step with the formula in
LaTeX and the numbers substituted, statistic, df, raw p, BH-adjusted
p, effect size with its interpretation band (small/medium/large),
and a conclusion at alpha=0.05 that states significance AND effect
size. Store enough that the UI can re-compute the conclusion at any
alpha without calling the backend.
Rules: exclude id columns, the target, and categoricals with > 20
levels; Fisher's exact for 2x2 with any expected < 5; merge rare
levels otherwise; Shapiro on a sample of <= 5,000; cap at 40 tests.
Tests (tolerance 1e-9): chi-square statistic, p and expected table vs
scipy.stats.chi2_contingency (correction=False for >2x2 AND check the
2x2 Yates behaviour is explicit and documented); Welch t vs
scipy.stats.ttest_ind(equal_var=False); Mann-Whitney vs
scipy.stats.mannwhitneyu (same alternative); BH vs
statsmodels.stats.multitest.multipletests(method="fdr_bh");
Cramér's V and Cohen's d vs hand-calculated values on a tiny table;
Fisher fallback triggers; a constant column is skipped, not crashed.
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 4: Modelling, SHAP, odds ratios, predictions

### Task T4.1: Train and evaluate

```text
Phase 4, step 1. Implement stats/modelling.py + modelling_node per
SPEC. Build one sklearn Pipeline per model (ColumnTransformer: median
impute + StandardScaler for numerics; most_frequent impute + OneHot
handle_unknown="ignore" for categoricals). Exclude id columns and the
time column only if it is derived from the target. Stratified 80/20
split, random_state=42, split BEFORE fitting any transformer.
Models: LogisticRegression(class_weight="balanced", max_iter=2000) and
HistGradientBoostingClassifier(class_weight="balanced").
5-fold stratified CV on train (ROC-AUC, PR-AUC). Pick the best by CV
PR-AUC. Evaluate ONCE on test: accuracy, precision, recall, F1,
ROC-AUC, PR-AUC, confusion matrix, ROC curve points (<= 100).
Leakage guard: raise a clear error if test ROC-AUC > 0.99, and warn if
any single feature has |correlation| > 0.9 with the target.
Permutation importance on test (n_repeats=10, random_state=42),
mapped back to ORIGINAL column names (not one-hot names).
Tests: Telco reaches ROC-AUC >= 0.80; a planted leaky column trips
the guard; results are identical across two runs.
Apply the Standard Task Protocol (section 2).
```

### Task T4.2: SHAP and odds ratios

```text
Phase 4, step 2.
SHAP: explain the gradient boosting model on the transformed test
matrix (sample <= 2,000 rows). Use shap.TreeExplainer if it supports
the model; otherwise fall back to shap.Explainer with a 100-row
background and say which was used. Aggregate one-hot columns back to
their original feature. Store: global mean |SHAP| per feature, and
summary points (downsampled) for a beeswarm-style chart.
Odds ratios: statsmodels Logit on the training data (numerics
standardised, categoricals one-hot with drop_first and a documented
reference level). Report OR, 95% CI, p-value per term, labelled "per 1
SD" for numerics and "vs <reference level>" for categoricals. Handle
perfect separation and singular matrix errors by dropping the
offending term with a logged warning, never crashing.
Build a driver_impact table joining: permutation importance rank,
mean |SHAP|, OR with CI, and the matching hypothesis test's adjusted p.
Tests: OR = exp(coef) and CI = exp(coef ± 1.96·SE) match statsmodels
within 1e-9; one-hot aggregation sums correctly; separation is
handled.
Apply the Standard Task Protocol (section 2).
```

### Task T4.3: Per-customer predictions

```text
Phase 4, step 3. Score ALL customers with the chosen model. For each:
id, churn probability (3 dp), risk band (High >= 0.6, Medium >= 0.3,
Low; thresholds from config), and top 3 SHAP reasons in plain English
(e.g. "Month-to-month contract (+0.18)"). Write predictions to
DATA_DIR/{id}/predictions.parquet and store only the path + band
counts in state. Add GET /results/{id} returning all results JSON
(predictions paginated, 100 per page, filterable by band).
Tests: every customer gets exactly 3 reasons (or fewer only if fewer
features exist); band counts sum to total; pagination works.
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 5: Impact, insight, recommendation, validator agents

### Task T5.1: Compact results + impact node

```text
Phase 5, step 1.
(a) Write graph/results_digest.py: build a compact JSON (< 12k
tokens) from state for the LLM: data_health summary, top churn rates
by category, segment profiles, significant tests (adjusted p) plus the
5 strongest non-significant ones, model metrics, driver_impact table,
survival medians. Every value keeps a stable dot-path key
(e.g. "hypothesis_results.Contract.cramers_v").
(b) Implement impact_node (Python only): for each segment and each
significant categorical level, compute customers affected, current
churn rate, churners, revenue at risk if a monthly revenue column was
confirmed, and expected churners saved under 10% and 25% relative
churn reduction. Store under impact_estimates with keys and explicit
assumption text.
Tests: digest stays under the token budget on Telco; every key in the
digest resolves in state; impact maths checked by hand on a tiny
example.
Apply the Standard Task Protocol (section 2).
```

### Task T5.2: Prompt files

```text
Phase 5, step 2. Create backend/app/prompts/insight_agent.v1.md and
recommendation_agent.v1.md, and a small loader that reads a prompt by
name+version and fills variables. Each file has: version header, role,
task, input schema, output JSON schema, rules, and 2 few-shot examples
built from a tiny fake digest (not Telco, to avoid copying numbers).
Rules in both: "Use only numbers from the provided JSON. Every figure
must be listed in figures[] with its exact source_key and value. If a
result is not statistically significant, say so. Associations are not
causes; say 'associated with', never 'causes'."
Recommendation rules add: "Use impact numbers only from
impact_estimates. State the assumption. Priority = impact vs effort."
Tests: loader fails loudly on a missing variable; each file parses and
contains every required section.
Apply the Standard Task Protocol (section 2).
```

### Task T5.3: Insight + recommendation agents

```text
Phase 5, step 3. Implement insight_agent (temperature 0) and
recommendation_agent (temperature 0.3) with with_structured_output
and Pydantic models:
Insight {id, title, text, figures:[{source_key, value, display}],
significant: bool, causality_note}; exactly 10 or fewer if data is thin.
Recommendation {id, problem, action, target_segment,
customers_affected, impact:{source_key, value, assumption}, effort:
low|medium|high, priority: 1-5, group: quick_win|medium_term|strategic,
figures[]}.
If state contains validator feedback for this agent, include it in the
prompt as "Fix these issues: ...". Timeout 60 s, 2 retries with
backoff, and on final failure append to errors and return an empty list
(the dashboard still renders). Log token usage per call.
Tests with a mocked LLM: feedback is included on retry; a malformed
response is rejected; failure path returns empty without crashing.
Apply the Standard Task Protocol (section 2).
```

### Task T5.4: Validator node

```text
Phase 5, step 4. Implement validator_node:
1. For every figure: resolve source_key in state (dot path, list
indexes allowed). Missing key = fail.
2. Compare value with tolerance: relative 1% or absolute 0.005,
accepting fraction vs percent (0.265 == 26.5%) and rounding.
3. Scan each text field for numbers (regex handles %, commas, ₹, x, and
decimals). Any number not matching a declared figure = fail.
Ignore list numbers like "top 3" and years only if declared as such.
4. Recommendation impact must come from impact_estimates keys.
5. On failures: write feedback per agent and route back to that agent;
max 2 retries each (retry_counts). After that, drop only the
failing items, log a warning, and continue to report.
Write validation_report {checked, passed, failed, dropped, details}.
Tests: a correct insight passes; a planted wrong number fails; an
unlisted number in text fails; 26.5% vs 0.265 passes; retry limit
stops the loop; routing goes back to the right agent.
Apply the Standard Task Protocol (section 2).
```

### Task T5.5: Real end-to-end check (human approved)

```text
Run the full graph on the Telco sample with the REAL Gemini API, once,
only after the human approves (S5). Report: total runtime, number of LLM
calls, input/output tokens per agent, validator pass/fail counts, and
the 10 insights. Save the report to docs/runs/phase5_telco_run.md
(no secrets). Fix any failure found, then re-run the mocked test suite.
```

**HUMAN STOP S5: human approves the real run and reviews the output.**

Then run the Phase Gate.

## Phase 6: Frontend dashboard + live progress (MVP)

### Task T6.1: Typed API contract

```text
Phase 6, step 1. Generate TypeScript types from the FastAPI OpenAPI
schema (openapi-typescript) into frontend/lib/api-types.ts, with an
npm script "gen:types". Build lib/api.ts: typed functions for every
endpoint, a 30 s timeout, clear error objects for 4xx/5xx, and a
special case for 410 (session expired). Add a React hook
useProgressStream(sessionId) using EventSource that handles: node
events, awaiting_confirmation, errors, heartbeat, done, and automatic
reconnect with a max of 5 attempts. Close the stream on unmount.
Tests (vitest): the hook parses each event type; 410 maps to the
expired state.
Apply the Standard Task Protocol (section 2).
```

### Task T6.2: Upload, progress, schema confirmation, data health

```text
Phase 6, step 2. Build the pre-dashboard flow:
1. Upload page: drag-drop, file type/size check in the browser too,
sheet picker for xlsx, "Try sample data" button, anonymised-data
warning.
2. Live progress view: a vertical stepper of graph nodes (pending /
running / done / skipped / failed) driven by the SSE hook, parallel
nodes shown side by side.
3. Schema confirmation screen when awaiting_confirmation arrives:
table of columns with editable type dropdowns, target + positive
label pickers, id and time column pickers, the AI's reasoning, and
Confirm. Show server-side validation errors inline.
4. Data Health screen: health score, cleaning log table, missing %
bar chart, class balance.
Every screen has loading, empty and error states. Mobile-friendly.
Apply the Standard Task Protocol (section 2).
```

### Task T6.3a: Executive Overview tab

```text
Phase 6, step 3a: build the Executive Overview tab only, per docs/SPEC.md.
Contents: KPI cards (customers, churn rate, high-risk count, revenue at risk, model ROC-AUC), top 3 insights, top 3 recommendations, validator badge (e.g. "42/42 figures verified").
Use Recharts for charts, with axis titles and units, tooltips, and a
colour-blind-safe palette. Numbers formatted consistently (%, 2 dp for
stats, p < 0.001 shown as "< 0.001"). Every chart has a one-line
"what this shows" caption. Components are small and in
components/<tab>/. Loading, empty and error states. Works at 375 px
width. Do not modify other tabs.
Apply the Standard Task Protocol (section 2).
```

### Task T6.3b: Churn Drivers tab

```text
Phase 6, step 3b: build the Churn Drivers tab only, per docs/SPEC.md.
Contents: metrics table + confusion matrix, ROC curve, permutation importance bar chart, SHAP summary, odds ratio forest plot with CI whiskers, driver impact table.
Use Recharts for charts, with axis titles and units, tooltips, and a
colour-blind-safe palette. Numbers formatted consistently (%, 2 dp for
stats, p < 0.001 shown as "< 0.001"). Every chart has a one-line
"what this shows" caption. Components are small and in
components/<tab>/. Loading, empty and error states. Works at 375 px
width. Do not modify other tabs.
Apply the Standard Task Protocol (section 2).
```

### Task T6.3c: Hypothesis Testing tab

```text
Phase 6, step 3c: build the Hypothesis Testing tab only, per docs/SPEC.md.
Contents: summary table (variable, test, statistic, adjusted p, effect size, significant?), an alpha slider that re-computes significance client-side, each row expands into the full step-by-step calculation rendered with KaTeX (H0/H1, assumption checks, observed/expected tables, formulas with substituted numbers, conclusion).
Use Recharts for charts, with axis titles and units, tooltips, and a
colour-blind-safe palette. Numbers formatted consistently (%, 2 dp for
stats, p < 0.001 shown as "< 0.001"). Every chart has a one-line
"what this shows" caption. Components are small and in
components/<tab>/. Loading, empty and error states. Works at 375 px
width. Do not modify other tabs.
Apply the Standard Task Protocol (section 2).
```

### Task T6.3d: Risk Predictions tab

```text
Phase 6, step 3d: build the Risk Predictions tab only, per docs/SPEC.md.
Contents: paginated server-side table, filter by band, search by ID, reasons shown as chips, CSV download of the current filter.
Use Recharts for charts, with axis titles and units, tooltips, and a
colour-blind-safe palette. Numbers formatted consistently (%, 2 dp for
stats, p < 0.001 shown as "< 0.001"). Every chart has a one-line
"what this shows" caption. Components are small and in
components/<tab>/. Loading, empty and error states. Works at 375 px
width. Do not modify other tabs.
Apply the Standard Task Protocol (section 2).
```

### Task T6.3e: Recommendations tab

```text
Phase 6, step 3e: build the Recommendations tab only, per docs/SPEC.md.
Contents: cards grouped into Quick wins / Medium-term / Strategic, sorted by priority; each shows problem, action, segment, customers affected, impact with its assumption, and effort.
Use Recharts for charts, with axis titles and units, tooltips, and a
colour-blind-safe palette. Numbers formatted consistently (%, 2 dp for
stats, p < 0.001 shown as "< 0.001"). Every chart has a one-line
"what this shows" caption. Components are small and in
components/<tab>/. Loading, empty and error states. Works at 375 px
width. Do not modify other tabs.
Apply the Standard Task Protocol (section 2).
```

### Task T6.3f: Customer Insights tab

```text
Phase 6, step 3f: build the Customer Insights tab only, per docs/SPEC.md.
Contents: churn rate by category charts, numeric comparisons, correlation heatmap, segment profile cards, survival curves (if available), the top 10 insights list with non-significant ones visibly marked.
Use Recharts for charts, with axis titles and units, tooltips, and a
colour-blind-safe palette. Numbers formatted consistently (%, 2 dp for
stats, p < 0.001 shown as "< 0.001"). Every chart has a one-line
"what this shows" caption. Components are small and in
components/<tab>/. Loading, empty and error states. Works at 375 px
width. Do not modify other tabs.
Apply the Standard Task Protocol (section 2).
```

### Task T6.4: End-to-end check

```text
Add a Playwright test that runs the full Telco sample flow against a
locally running backend with the LLM mocked: upload sample, confirm
schema, wait for done, open every tab, and assert key elements are
visible and no console errors occur. Add it to CI as a separate job
that runs on PRs to main.
Apply the Standard Task Protocol (section 2).
```

**HUMAN STOP S6: human reviews the MVP locally.**

Then run the Phase Gate.

## Phase 5b: Next best offer

If the Telco sample has no offer columns, first generate a synthetic offers dataset (with a no-offer control group) at backend/sample_data/offers_sample.csv and use it for these tests.

### Task T5b.1: Detect and reshape offer data

```text
Phase 5b, step 1. Extend schema_agent and its prompt (bump to v2, keep v1) to
propose offer columns: offer_shown, offer_accepted, offer_date,
offer_cost. Heuristics first (names containing offer, promo, campaign,
clicked, accepted, redeemed). The user confirms them in human_review.
In stats/offers.py write reshape_offers(df) that converts any shape to
a long table (customer_id, offer, accepted, offer_date): one column
per offer with 0/1, a delimited list in one cell ("Data pack;
Cashback", comma or semicolon), or one offer + one accepted column.
Normalise offer names (trim, case) and build offer_catalog from what
exists in the data; never invent offers.
Tests: all three input shapes produce the identical long table;
blank cells mean no offer; unknown delimiters are handled; the
no-offer-columns case skips cleanly.
Apply the Standard Task Protocol (section 2).
```

### Task T5b.2: Offer effectiveness analysis

```text
Phase 5b, step 2. Implement offer effectiveness in stats/offers.py
(Python only, no LLM). For each offer, overall and per segment:
customers shown, acceptance rate, churn rate among acceptors vs
non-acceptors vs never-offered, with n for every cell.
Run chi-square (Fisher's exact when expected < 5) on accepted x
churned per offer and add them to the Benjamini-Hochberg family.
Leakage guard: if offer_date exists, keep only offers before the
churn event or observation cutoff; if it doesn't, add a visible
warning to data_health.
Selection-bias check: compare the average churn probability (from
Phase 4) of offered vs never-offered customers; if offered customers
were much riskier, add a warning that raw comparisons understate the
offer's effect.
Tests: rates checked by hand on a tiny table; the leakage filter drops
post-churn offers; the bias warning fires on a constructed example.
Apply the Standard Task Protocol (section 2).
```

### Task T5b.3: Next-best-offer scoring

```text
Phase 5b, step 3. Implement offer_node:
1. Per offer with >= 50 exposures: train a LogisticRegression
(class_weight="balanced") predicting P(accept | customer features),
using the Phase 4 preprocessing pipeline. Report ROC-AUC per offer
model; offers with too little data use their segment's acceptance
rate instead, flagged as "low data".
2. P(stay | accepted) per offer and segment from the effectiveness
table, with Laplace smoothing so small cells aren't 0% or 100%.
3. For each Medium/High-risk customer and each eligible offer:
expected_value = P(churn) * P(accept) * P(stay | accepted)
* customer_value - offer_cost
customer_value = monthly revenue x a configurable horizon (default
12 months) if revenue exists; otherwise rank by expected customers
saved and say so.
4. Eligibility rules from config: max discount 20%, no offer the
customer already declined in the last 30 days, and a no-offer
option if every offer has negative expected value.
5. Store per customer: best offer, runner-up, expected value, the
inputs used, and the assumptions, in predictions.parquet. Add an
offer summary to the results digest with source_keys.
Tests: expected value maths by hand; no-offer chosen when all values
are negative; declined-offer rule works; only catalogue offers are
ever recommended; results are reproducible.
Apply the Standard Task Protocol (section 2).
```

### Task T5b.4: Personalised message + validation + UI

```text
Phase 5b, step 4.
(a) Add prompts/offer_message.v1.md: the LLM gets ONE customer's
top 3 reasons, chosen offer, and plan details from state, and writes a
2-sentence retention message (plus an SMS version under 160
characters). It must not change the offer, discount, or any number.
Generate messages only on demand for a selected customer (not for
all customers), with a cache per customer.
(b) The validator checks every number in the message against the
chosen offer's source_keys.
(c) UI: in Risk Predictions add "Next best offer" and "Expected
value" columns, and in the row detail a "Why this offer" panel
showing the formula with its inputs substituted (KaTeX) plus a
"Generate message" button. In Recommendations add an "Offer
performance" card group from the effectiveness table.
(d) Update the README limitations: "Recommendations show association,
not proven causation; validate with an A/B test before rollout."
Tests: a message with a changed discount fails validation; the SMS
stays under 160 characters; the cache prevents repeat LLM calls.
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 5c: A/B testing

### Task T5c.1: Experiment model + sample size

```text
Phase 5c, step 1. Create backend/app/experiments/ with SQLAlchemy models:
Experiment {id, name, hypothesis, source_recommendation_id, segment
definition, offer, primary_metric (churn within N days), guardrail
metrics (complaints, ARPU), baseline_rate, mde (absolute), alpha,
power, control_share, n_required_per_arm, planned_start, planned_end,
status, created_by, approved_by, approved_at, decision, decision_note,
data_snapshot_hash} and an append-only AuditLog of every status
change. Alembic migration. Works on SQLite and Postgres.
Implement stats/experiment_design.py: sample size per arm for a
two-proportion test from baseline churn rate, MDE, alpha, power and
control share, using statsmodels (proportion_effectsize +
NormalIndPower.solve_power with the ratio argument). Also return: the
smallest detectable effect for the customers actually available in
the segment, and the expected duration if the user enters a monthly
volume. If the segment is too small, say so plainly and suggest a
larger MDE or a wider segment.
Tests: sample size matches statsmodels exactly; the unequal split
(e.g. 80/20) is handled; a segment too small triggers the warning;
invalid inputs (mde <= 0, alpha outside 0-0.2) are rejected.
Apply the Standard Task Protocol (section 2).
```

### Task T5c.2: Approval gate + randomised assignment

```text
Phase 5c, step 2.
(a) Endpoints: POST /experiments (create draft from a
recommendation), PATCH /experiments/{id} (edit, only while draft),
POST /experiments/{id}/approve (requires approver name + a checkbox
confirming the offer cost and eligibility were reviewed; locks the
design), POST /experiments/{id}/assign, GET /experiments/{id}.
(b) Assignment: deterministic randomisation by hashing
(experiment_id + customer_id) with SHA-256 into [0,1) compared to
control_share, so the same customer always lands in the same group.
Exclude customers already in another running experiment. After
assigning, run a balance check: compare treatment vs control on churn
probability, tenure, ARPU and plan type (standardised mean
difference; flag any |SMD| > 0.1). Store the assignment and the
data_snapshot_hash.
(c) Export assignment CSV: customer_id, group, offer (blank for
control), message (treatment only, if generated).
Tests: editing an approved experiment is rejected (409); assignment is
reproducible across runs; the split is within 1 percentage point of
the target on 10,000 IDs; the balance check flags a deliberately
skewed split; overlapping experiments are prevented.
Apply the Standard Task Protocol (section 2).
```

### Task T5c.3: Results upload + analysis

```text
Phase 5c, step 3. POST /experiments/{id}/results accepts a CSV:
customer_id, group, offer_accepted (treatment only), churned (0/1
within the planned window), optional revenue, optional complaints.
Validate: IDs and groups match the stored assignment exactly (report
mismatches), no duplicates, outcome window respected. Warn if uploaded
before planned_end ("early look: results may be unreliable").
Implement stats/experiment_analysis.py, all computed in Python:
1. Sample ratio mismatch (SRM): chi-square goodness of fit of
observed vs planned split; if p < 0.001 flag "results not
trustworthy" and block the ship decision.
2. Primary metric, intention-to-treat (everyone assigned): churn rate
per arm with Wilson 95% CIs, absolute difference with a 95% CI
(Newcombe method), relative lift, two-proportion z-test p-value,
and achieved power at the observed sample size.
3. Business impact: customers saved = (control rate - treatment rate)
x treatment n, with a CI; net value = saved x customer_value -
offer cost x acceptors; state all assumptions.
4. Per-protocol view (acceptors vs control), clearly labelled as
biased and secondary.
5. Guardrails: complaints and ARPU per arm with CIs.
6. Segment breakdown ONLY for segments pre-registered in the design,
BH-corrected, labelled exploratory.
7. Decision helper (not a decision): "ship" if the CI of the
difference excludes 0 in the good direction, net value > 0 and no
guardrail breached; "don't ship" if the CI excludes 0 in the bad
direction or net value < 0; otherwise "inconclusive" with the
extra sample needed.
Every number gets a source_key.
Tests (tolerance 1e-9): z-test and Wilson CIs match
statsmodels.stats.proportion (proportions_ztest, proportion_confint
method="wilson"); Newcombe CI matches a hand-worked textbook example;
SRM fires on a 60/40 split planned as 50/50; a mismatched ID is
reported.
Apply the Standard Task Protocol (section 2).
```

### Task T5c.4: Summary, decision gate, feedback loop, UI

```text
Phase 5c, step 4.
(a) prompts/experiment_summary.v1.md: the LLM gets the analysis JSON
and writes a 5-sentence plain-English summary for a retention manager,
stating the result, its uncertainty, business impact, guardrails and
any warnings. It must not recommend beyond the decision helper.
The validator checks every figure.
(b) POST /experiments/{id}/decide: ship | don't ship | extend, with a
required note and decider name; blocked if SRM failed; stored in the
audit log.
(c) Feedback loop: when an experiment is decided, write its measured
effect into an offer_evidence table; offer_node prefers
experiment-measured P(stay | offered) over observational estimates,
and the UI labels each offer "experiment-proven" or "observational".
(d) Experiments tab: a list with status chips; a design wizard with
live sample-size feedback as MDE/power sliders move; an approval
screen; a results view with per-arm rate bars and CI whiskers, a
forest plot of the difference (overall + pre-registered segments), an
SRM/balance/guardrail health strip, the validated summary, the
decision-helper verdict and the decision form; and the audit trail.
Tests: deciding before results is rejected; SRM blocks "ship"; the
feedback loop changes the next-best-offer inputs; an
"experiment-proven" label appears after a decision.
Apply the Standard Task Protocol (section 2).
```

### Task T5c.5: Prove it works with a known answer

```text
Phase 5c, step 5. Write scripts/simulate_experiment.py: take an
approved experiment's assignment and generate a results file with a
KNOWN true effect (e.g. control churn 26%, treatment 21%, 45%
acceptance), seed 42. Add 3 scenarios: real effect, no effect, and a
broken 60/40 delivery. Add tests asserting the app finds the effect
(CI contains the true difference) in scenario 1, returns
"inconclusive" or "don't ship" in scenario 2, and blocks on SRM in
scenario 3. Use scenario 1 in the demo and add it to "Try sample data".
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 5d: Metrics layer (model, business, telemetry)

Principle: Python computes every number; the LLM only explains numbers present in state; the browser only displays them. Details are in SPEC v1.3 additions (Appendix B).

### Task T5d.0: Plan the metrics layer (no code)

```text
Read CLAUDE.md, docs/SPEC.md (including the v1.3 additions) and
docs/PROGRESS.md. Do not write code. Produce, in PROGRESS.md under
"Phase 5d plan":
1. Every file to create or change, with each function's signature and
   one-line purpose.
2. New state keys and their reducers; new API endpoints and response
   shapes; new config files (offers.yaml, pricing.yaml) with an example.
3. What you will reuse from Phases 4, 5b and 5c (test split, predictions,
   experiment_design.py, offer evidence) and what is new. If a reused
   piece doesn't exist yet, say you will create it in its final location.
4. Risks and how you'll handle them, at least: calibration of
   class-weighted models, missing ARPU column, offers.yaml rules that
   reference absent columns, parallel-node telemetry writes, stale LLM
   explanations after assumption edits, Plotly bundle size / SSR.
5. The test list for every task below, with the expected reference values.
Then STOP (S8) and wait for the human's go-ahead.
```

**HUMAN STOP S8: human approves the Phase 5d plan.**

### Task T5d.1: Model metrics + calibration

```text
Phase 5d, step 1. Create backend/app/stats/model_metrics.py (pure
functions, dict in/dict out, JSON-serialisable) computing, on the
held-out test split from Phase 4 only: ROC-AUC, PR-AUC (average
precision), precision and recall at top 10%, lift by decile and
cumulative gains, Brier score, calibration curve (10 uniform bins with
counts). Add calibration: CalibratedClassifierCV on the training split
only (isotonic if n_train >= 1000 else sigmoid, cv=5); store calibrated
probabilities for all customers and report Brier + calibration for raw
and calibrated. Store under state key model_metrics_v2 with source_keys.
Tests (tolerance 1e-9 unless stated): ROC-AUC vs
sklearn.metrics.roc_auc_score; PR-AUC vs average_precision_score; Brier
vs brier_score_loss; calibration curve vs
sklearn.calibration.calibration_curve(n_bins=10); precision/recall@10%
and decile lift vs hand-computed values on a 20-row fixture with ties;
the test split is never touched by calibration fitting (assert index
disjointness); calibrated Brier <= raw Brier on the Telco sample.
Apply the Standard Task Protocol (section 2).
```

### Task T5d.2: Offer catalogue + business metrics

```text
Phase 5d, step 2. Create backend/app/config/offers.yaml (4-6 example
offers matching SPEC v1.3 fields; ARPU-agnostic costs) and a Pydantic
loader that validates it and reports errors with the offending line.
Create backend/app/stats/business_metrics.py with:
- revenue_at_risk(df, p, arpu_col, months_remaining=12)
- eligible_offers(customer, catalogue, schema) using the segment rules
- expected_saving(p, arpu, months_remaining, offer) exactly per SPEC v1.3
- next_best_offer(...) -> best offer, runner-up, expected_saving, or
  "No offer" when best <= 0
- offer_roi_by_segment(...)
Every result carries an ASSUMPTIONS block (months_remaining, each
offer's acceptance / save rate / cost, their source). Prefer Phase 5b/5c
data-driven estimates when present (source = "data"). If no ARPU column
is confirmed, return a disabled result with a clear reason.
Tests: a 5-row fixture with hand-computed revenue_at_risk and
expected_saving for every customer x offer; "No offer" when all savings
<= 0; ineligible offers excluded; a rule referencing a missing column
skips that offer with a warning; setting save_rate=1 and
cost_basis="per_targeted" reproduces p*acceptance*ARPU*12 - cost;
months_remaining edits change results linearly; invalid YAML gives a
clear error.
Apply the Standard Task Protocol (section 2).
```

### Task T5d.3: A/B test plan

```text
Phase 5d, step 3. In backend/app/stats/experiment_design.py (create it,
or extend it if Phase 5c already did) implement
sample_size_two_proportions(p1, relative_lift, alpha=0.05, power=0.8,
ratio=1.0) per SPEC v1.3 using statsmodels proportion_effectsize +
NormalIndPower.solve_power, rounded up. Return: n_per_arm, total_n, p1,
p2, cohens_h, z_alpha, z_beta, formula_latex
(n = ((z_{1-alpha/2} + z_{1-beta}) / h)^2, h = 2 arcsin sqrt(p1) - 2 arcsin sqrt(p2)),
and an ASSUMPTIONS block. business_metrics.ab_plan(segment) uses the
segment's observed churn rate as p1 and warns if the segment has fewer
customers than 2 x n_per_arm.
Tests: textbook reference p1 = 0.20, p2 = 0.15 (relative lift 0.25),
alpha 0.05 two-sided, power 0.8 -> 903 per arm (statsmodels 902.34,
rounded up); a second reference p1 = 0.26, relative lift 0.20 -> 1038 per
arm; lift <= 0 or >= 1, p1 outside (0,1), and power outside (0,1)
raise clear ValueErrors; ratio != 1 matches solve_power(ratio=...).
Apply the Standard Task Protocol (section 2).
```

### Task T5d.4: Run telemetry

```text
Phase 5d, step 4. Create backend/app/graph/telemetry.py:
- a node decorator appending one event per node run to
  state.telemetry_events (Annotated[list, operator.add], safe under the
  parallel fan-out): node, started_at, latency_ms, status, retries,
  input_tokens, output_tokens, model.
- token capture from the Gemini wrapper's usage metadata (extend
  backend/app/llm.py to return usage; never log prompt text).
- schema_corrections: count and list fields where the human's confirmed
  schema differs from the AI proposal (computed in /confirm-schema).
- summarise_run(state) -> validator pass/fail, figures caught, retries
  per agent, schema corrections, latency per node and total, tokens per
  model, estimated cost from backend/app/config/pricing.yaml
  (labelled ESTIMATE; default prices 0 with note "free tier").
- persist each run summary to a runs table (SQLAlchemy + Alembic, same
  database as experiments).
Tests: parallel nodes append events without InvalidUpdateError; latency
recorded for every node including skipped ones (status "skipped"); token
sums match a mocked wrapper; cost = tokens x price computed by hand;
schema corrections counted on a fixture; summaries persist and list.
Apply the Standard Task Protocol (section 2).
```

### Task T5d.5: API + upload error handling

```text
Phase 5d, step 5. Add endpoints: GET /metrics/model/{id},
GET /metrics/business/{id}, POST /metrics/business/{id} (validated
assumptions body: months_remaining 1..60, per-offer overrides of
acceptance/save rate/cost, relative_lift 0.01..0.9, alpha, power;
recomputes in Python, no LLM, target < 1 s on 10k rows), GET
/telemetry/{id}, GET /telemetry/runs?limit=50. Regenerate the frontend
types (npm run gen:types).
Upload errors per SPEC v1.3: no binary target candidate, one class only,
fewer than MIN_ROWS rows. Each returns 422 with a plain-English message
and what to do; the graph never starts.
Tests: API tests for each endpoint (happy path, unknown session 410,
invalid assumptions 422); uploads with no churn column, one class only,
49 rows and MIN_ROWS - 1 rows each return 422 with the expected message.
Apply the Standard Task Protocol (section 2).
```

### Task T5d.6: Frontend: Model Performance, Business Impact, Agent Health

```text
Phase 5d, step 6. Add react-plotly.js + plotly.js-basic-dist-min, loaded
via next/dynamic with ssr: false through one components/charts/PlotlyChart
wrapper (theme, responsive, loading state). Build three tabs:
- Model Performance: KPI cards (ROC-AUC, PR-AUC, precision@10%,
  recall@10%, Brier) with plain-English tooltips (e.g. "Of the 10% of
  customers we flag, this share actually churned"); ROC curve; PR curve;
  lift by decile bars + cumulative gains; calibration plot (raw vs
  calibrated vs perfect line). Move the metrics part of Churn Drivers here.
- Business Impact: KPI cards (revenue at risk, expected saving, customers
  with an offer, overall ROI); an Assumptions panel (months remaining,
  per-offer acceptance/save rate/cost, MDE lift, power) that posts to
  the API (debounced 400 ms) and re-renders; ROI by segment chart;
  next-best-offer table; A/B plan card showing the formula (KaTeX), inputs
  and n per arm; every assumption visibly labelled ASSUMPTION with its
  source; the "Based on default assumptions" banner + "Regenerate
  explanation" button when edited.
- Agent Health: validator pass rate, figures caught, retries, schema
  corrections, latency per node (bar), tokens and ESTIMATED cost, and a
  trend of the last 50 runs.
The browser does no metric maths. Loading, empty and error states; 375 px
width. Extend the Playwright e2e test to open all three tabs and edit one
assumption.
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 7: Chat agent + exports

### Task T7.1: Tool-only chat agent (Ask the Data tab)

```text
Phase 7, step 1. Build the chat agent as a separate LangGraph ReAct
graph in agents/chat_agent.py with tools: get_stat(key),
get_segment(id), get_test_result(variable), get_customer_risk(id),
filter_and_aggregate(filters, group_by, metric, column).
filter_and_aggregate validates every argument with Pydantic: columns
must exist; ops limited to ==, !=, >, >=, <, <=, in; metrics limited to
count, mean, median, sum, churn_rate; max 3 filters; result capped at
50 rows. No exec, eval, df.query, or string-built code.
System prompt in prompts/chat_agent.v1.md: answer only from tool
results, cite the tool used, say clearly when something wasn't
computed, refuse questions unrelated to the dataset. Max 6 tool calls
per question; keep the last 10 messages per session.
POST /chat/{id}, rate limited per IP.
Tests: a filter on a non-existent column is rejected; an injection
attempt ("ignore rules and run os.system") gets a refusal and no tool
abuse; an uncomputed metric gets "not computed"; the tool-call cap
holds.
Apply the Standard Task Protocol (section 2).
Also build the Ask the Data tab UI: message list, input, loading state,
and the tool used shown under each answer.
```

### Task T7.2: Exports

```text
Phase 7, step 2. Implement report_node + GET /export/{id}/pdf and
/excel.
Excel (openpyxl): sheets Cleaned_Data, Predictions (with reasons),
Hypothesis_Tests, Drivers, Recommendations; a header row, frozen
panes, proper number formats, one table per sheet (Power BI-ready,
no merged cells).
PDF (reportlab or WeasyPrint; pick one and explain; install system
deps in the Dockerfile if needed): cover page, executive summary,
key charts rendered as images, top insights, recommendations, a
methodology + limitations page, and the validator summary.
Files written to the session folder; generated on demand, not in
the main graph run, to keep analysis fast.
Tests: the Excel opens and has the expected sheets and row counts;
the PDF is non-empty and has the expected page count range.
Apply the Standard Task Protocol (section 2).
```

Then run the Phase Gate.

## Phase 8: Production hardening, deploy, README

### Task T8.1: Production hardening

```text
Phase 8, step 1. Prepare for production:
- render.yaml: one Docker web service, healthCheckPath /health,
env vars declared with sync: false for secrets.
- Dockerfile: multi-stage, slim, non-root, uvicorn with 1 worker
(the in-process SSE and background tasks need a single process),
PORT from env.
- CORS: allow FRONTEND_ORIGIN plus an optional regex for your Vercel
preview URLs (FRONTEND_ORIGIN_REGEX).
- Structured JSON logging with session_id; never log file contents
or API keys.
- Rate limits on /upload and /chat.
- Frontend: a friendly "Waking up the server (up to a minute)…"
state when /health is slow, since the free backend sleeps when idle.
Build and run the Docker image locally and run the Telco flow
against it before we deploy.
Apply the Standard Task Protocol (section 2).
```

### Task T8.2: Deploy (human does the dashboard steps)

```text
STOP (S7) and give the human these exact steps, then wait:
1. Render: New -> Blueprint -> select the churnlens repo (reads
   render.yaml). Set GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MODEL_FAST,
   GEMINI_RPM, and FRONTEND_ORIGIN (temporary value, fixed in step 3).
   Optional: DATABASE_URL (free Postgres, e.g. Neon or Supabase) so
   experiments and paused sessions survive restarts.
2. Vercel: Add New -> Project -> import the repo, Root Directory =
   frontend, NEXT_PUBLIC_API_URL = the Render URL. Deploy.
3. Render: set FRONTEND_ORIGIN to the Vercel production URL; redeploy.
4. Paste both URLs back here.
When the human replies: verify GET <render>/health, then run a smoke
check of the full sample flow against the live URLs (curl for the API;
describe what the human should click for the UI). Record the URLs in
PROGRESS.md and README.
```

**HUMAN STOP S7: human does the Render and Vercel steps.**

### Task T8.3: README + demo assets

```text
Phase 8, step 2. Write README.md: one-paragraph pitch, live demo link,
a Mermaid architecture diagram (frontend, backend, LangGraph flow,
LLM), a "How the agents stay honest" section (digest, source_keys,
validator), tech stack with one-line reasons, local setup, env var
table, deploy steps, tests + CI badge, limitations (sample data only,
sessions expire, free-tier cold starts), and a screenshots section
with placeholders. Also write docs/DEMO_SCRIPT.md: a 2-minute demo
walkthrough.
Apply the Standard Task Protocol (section 2).
```

Then run the final Phase Gate and tell the human: "ChurnLens build complete." with the live URL, test counts, and the Known issues list.

## 5. Change request: add the metrics layer mid-build (paste-ready)

If you are already part-way through the build, first replace docs/BUILD_RUNBOOK.md with this version (v1.3), then paste this into Claude Code:

```text
Read CLAUDE.md, docs/SPEC.md, docs/PROGRESS.md and docs/BUILD_RUNBOOK.md.
This runbook is now v1.3 and adds Phase 5d (metrics layer).
1. Update CLAUDE.md with rules 21-23 from Appendix A and append the
   "v1.3 additions" section from Appendix B to docs/SPEC.md. Show me
   the diff of both files.
2. Finish the task you are currently on (if any) and its tests.
3. Then run Task T5d.0 and STOP at S8 for my go-ahead.
After my go-ahead, run T5d.1 to T5d.6 with the Execution Protocol, run
the Phase Gate, run ALL tests, update PROGRESS.md, commit, and continue
with the remaining phases in the Execution order table.
```

## 6. Recovery prompts (for the human)

| Symptom | Paste this into Claude Code |
| --- | --- |
| Stuck on an error | Here is the full error: <paste>. Reproduce it with a failing test first, find the root cause, fix it, and show the test passing. Don't change the test to make it pass. |
| Going in circles | Stop. Summarise what you tried, then propose 2 hypotheses and how to test each before changing any more code. |
| Editing unrelated files | Stop. Revert changes outside the current task's files. Re-read CLAUDE.md rule 13 and redo only the task. |
| Context feels overloaded | Update docs/PROGRESS.md with exactly where you are, then tell me to run /clear. (Then send the Resume prompt.) |
| A phase is tangled | Abandon this phase branch, return to main, and restart the phase from its first task with a better plan. Record the lesson in PROGRESS.md. |
| Want to see status | Show me docs/PROGRESS.md: current task, completed tasks with test counts, known issues, and anything you need from me. |

## Appendix A: CLAUDE.md

```markdown
# ChurnLens
Agentic churn analysis app. Full spec: docs/SPEC.md. Progress: docs/PROGRESS.md.
Build plan: docs/BUILD_RUNBOOK.md (follow its Execution Protocol).

## Stack
- backend/: Python 3.11, FastAPI, LangGraph, langchain-google-genai, pandas,
scipy, statsmodels, scikit-learn, shap, lifelines. Deployed on Render (Docker).
- frontend/: Next.js (App Router), TypeScript strict, Tailwind, Recharts,
KaTeX. Deployed on Vercel, root directory = frontend.

## Non-negotiable rules
1. Secrets only in .env files or host env vars. Never in code, logs or git.
2. LLM model names come from env vars (GEMINI_MODEL, GEMINI_MODEL_FAST). Never hard-code.
3. The LLM never sees raw rows. Only column names, dtypes, 5 sample
values, and computed-results JSON.
4. The LLM never computes numbers. All statistics come from Python code.
The LLM only explains numbers that already exist in state.
5. All LLM output uses with_structured_output + Pydantic models.
6. Prompts live in backend/app/prompts/*.md with a version header.
No inline prompt strings.
7. Every graph node writes only its own state keys. List fields shared
by parallel nodes use reducers (Annotated[list, operator.add]).
8. Every node catches its own errors, appends to state.errors, and never
crashes the graph. A fatal error routes to error_node.
9. Every external call (LLM) has a timeout, retry with backoff on
429/5xx, and a safe fallback.
10. Statistical results are unit-tested against scipy/statsmodels
with a tolerance of 1e-9.
11. random_state=42 everywhere randomness exists.
12. No exec/eval anywhere. Pandas operations in the chat agent are
whitelisted.
13. Touch only files needed for the current task. Explain any new
dependency before adding it.
14. Before finishing any task: run ruff + pytest (backend), and
lint + typecheck + build (frontend). Show the real output.
15. At the end of each phase, update docs/PROGRESS.md.

## Gemini rules
16. All LLM calls go through one wrapper, backend/app/llm.py
(ChatGoogleGenerativeAI from langchain-google-genai). It owns model
choice, temperature, timeout, retries, throttling and token logging.
No node imports the SDK directly.
17. The wrapper throttles to GEMINI_RPM requests per minute and backs
off on 429 / RESOURCE_EXHAUSTED (free-tier limits are low).
18. A blocked or empty response (safety filter, finish reason not
STOP) is a failure: retry once, then use the node's fallback.
19. Keep structured-output schemas Gemini-friendly: flat objects, lists,
Literal/enum fields. No Dict[str, Any], deep unions or recursion.
20. Tests never call Gemini. Mock the wrapper.
21. The browser never computes metrics. Assumption edits go to the API and
    are recomputed in Python.
22. Every assumption-dependent output includes an ASSUMPTIONS block with
    source = default | user | data.
23. Money metrics use calibrated probabilities from the training split only.

## Commands
- backend: cd backend && source .venv/bin/activate && ruff check . && pytest -q
- frontend: cd frontend && npm run lint && npm run typecheck && npm run build
```

## Appendix B: docs/SPEC.md

```markdown
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

```
