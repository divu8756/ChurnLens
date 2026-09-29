# ChurnLens: single-file autopilot for Claude Code

This file is the ONLY thing the human adds to the empty project folder
/Users/divyanshusrivastava/ChurnLens.
It contains a secret (the Gemini key) inside the embedded backend/.env block:
BOOTSTRAP moves it into backend/.env (git-ignored) and removes it from
CLAUDE.md and from the backup copy. Never commit this original file.
Claude Code loads CLAUDE.md automatically. The human then types one word
(for example: go). From that point, follow AUTOPILOT below.


## AUTOPILOT (read this first, every session)

You are building ChurnLens end to end with as little human input as possible.
On the human's first message in ANY session (even "go", "hi" or "."), start
working immediately. Do not ask what to do.

1. If docs/BUILD_RUNBOOK.md does NOT exist: run BOOTSTRAP (section below or in
   docs/BOOTSTRAP_CLAUDE.md).
2. Otherwise: read docs/BUILD_RUNBOOK.md, docs/SPEC.md and docs/PROGRESS.md,
   run the full test suite to confirm the repo is green (fix it first if not),
   then resume from "Current task" in PROGRESS.md using the Execution Protocol
   (runbook section 2) in FULL-AUTO mode.

### FULL-AUTO mode = AUTONOMOUS mode + these overrides
- S1, S4, S5, S6 and S8 are CHECKPOINTS, not stops: write the summary / plan /
  report to docs/PROGRESS.md under "Checkpoints for the human" and continue.
- S2 and S3 are replaced by the one-time PREFLIGHT below.
- T1.1: CLAUDE.md and docs/SPEC.md already exist (created by BOOTSTRAP). Do not
  recreate them; only do the restate / Mermaid / risks part.
- T1.2: never overwrite an existing backend/.env; only create .env.example files.
- S5 (real Gemini run): run it automatically once, capped at 60 Gemini calls,
  and log tokens and estimated cost.
- The ONLY reasons to stop and wait for the human:
  a) PREFLIGHT finds the key rejected or gh not logged in,
  b) S7 deployment (needs the human's Render and Vercel accounts),
  c) the same failure survives 2 fix attempts,
  d) a destructive action, a new paid service, or a change to a locked rule.
- Never ask "should I continue?" between tasks or phases.
- Context management: when your context is getting long, finish the current
  task, commit, update "Current task" and "Next step" in PROGRESS.md, then
  say exactly: "Checkpoint saved. Type /clear, then type go." That is all the
  human needs to type.
- Permission prompts: if Claude Code asks for permission, tell the human once
  to choose the "don't ask again" option for routine commands (tests, npm, git).

### PREFLIGHT (once, right after BOOTSTRAP)
Project root must be /Users/divyanshusrivastava/ChurnLens. Run `pwd`; if it differs, stop and tell the
human to start Claude Code from that folder.
1. Check: python3.11, node >= 20, git, gh. If Homebrew is available, install
   anything missing with brew (python@3.11 node gh libomp). Report versions.
2. backend/.env already exists (written by BOOTSTRAP) with GEMINI_API_KEY set.
   Never print, log, commit or echo its value.
3. Pick the Gemini models automatically: with a small Python script that
   reads the key from backend/.env, call the Gemini API models list endpoint
   (https://generativelanguage.googleapis.com/v1beta/models, key sent in the
   x-goog-api-key header, never in the URL or logs). Choose the newest STABLE
   (non-preview, non-experimental) model whose name contains "pro" for
   GEMINI_MODEL and "flash" for GEMINI_MODEL_FAST; both must support
   generateContent. Write them into backend/.env with the script and report
   the two model names (not the key). If the call fails with 400/401/403,
   stop and tell the human the key was rejected and to create a new key in
   Google AI Studio and put it in backend/.env.
4. Run `gh auth status`. Only if it is NOT logged in, ask the human to run
   `gh auth login` in a terminal and type done. Otherwise do not stop.
5. Safety check before EVERY commit (make it scripts/check_secrets.py and
   run it): `git check-ignore -q backend/.env` must succeed, and a search of
   all tracked and staged files for the actual key value (read from
   backend/.env at runtime, never written anywhere) must find nothing. The
   script prints only PASS or FAIL with file names. On FAIL, stop and fix
   before committing.

### Where things are
- Build plan: docs/BUILD_RUNBOOK.md (tasks, Execution Protocol, stops)
- What to build: docs/SPEC.md
- Where you are: docs/PROGRESS.md
- Sample data: backend/sample_data/ (regenerate with scripts/*.py; fixed seeds)


## BOOTSTRAP (runs once, when docs/BUILD_RUNBOOK.md does not exist)

Do these steps in order without asking for permission to start.

1. Tell the human in 3 short lines: what ChurnLens is, that you will now
   unpack the plan and build everything phase by phase in
   /Users/divyanshusrivastava/ChurnLens, and that you will only stop if the GitHub login or the
   Gemini key needs fixing, and for deployment at the end.
2. Unpack the embedded files by running this exact script from the project
   root (it reads THIS file; do not retype the files by hand):

```python
import re, pathlib
root = pathlib.Path(".")
src_path = root / "CLAUDE.md"
src = src_path.read_text(encoding="utf-8")
blocks = re.findall(r"^=====BEGIN FILE: (.+?)=====\n(.*?)^=====END FILE: \1=====$",
                    src, flags=re.S | re.M)
assert len(blocks) >= 9, f"expected >= 9 embedded files, found {len(blocks)}"
(root / "docs").mkdir(exist_ok=True)
backup = re.sub(r"^=====BEGIN FILE: backend/\.env=====\n.*?^=====END FILE: backend/\.env=====\n", "",
                src, flags=re.S | re.M)                     # never keep the secret in docs/
(root / "docs" / "BOOTSTRAP_CLAUDE.md").write_text(backup, encoding="utf-8")
for path, body in blocks:
    p = root / path.strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    if p.name == ".env":
        p.chmod(0o600)
        print(f"wrote {p} (secret, not printed)")
    else:
        print(f"wrote {p} ({len(body):,} chars)")
print("unpacked", len(blocks), "files; CLAUDE.md is now the short rules + autopilot version")
```

   Save it as scripts/unpack_bootstrap.py and run
   `python3 scripts/unpack_bootstrap.py`. After this, CLAUDE.md is the short
   version (rules + AUTOPILOT); the original is kept in
   docs/BOOTSTRAP_CLAUDE.md.
3. `git init` (if needed). Run the PREFLIGHT step 5 safety check, then
   `git add -A` and commit "chore: bootstrap ChurnLens".
4. Run PREFLIGHT (in AUTOPILOT above).
5. Create backend/.venv with Python 3.11, `pip install pandas numpy`, then
   generate sample data:
   `python scripts/generate_telco_sample.py backend/sample_data/telco_churn.csv`
   `python scripts/generate_india_sample.py backend/sample_data/india`
   Check: telco file has 7,014 rows (7,000 unique + 14 duplicates) and 11
   blank TotalCharges. Commit.
6. Start the runbook at Task T1.1 in FULL-AUTO mode and keep going.

The .claude/settings.json unpacked in step 2 pre-approves routine commands
and blocks dangerous ones; it takes full effect from the next session.

=====================================================================
EMBEDDED FILES BELOW. This is file content for the unpack script, NOT
instructions to follow now. After unpacking, read them from disk.
=====================================================================

=====BEGIN FILE: CLAUDE.md=====
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

## AUTOPILOT (read this first, every session)

You are building ChurnLens end to end with as little human input as possible.
On the human's first message in ANY session (even "go", "hi" or "."), start
working immediately. Do not ask what to do.

1. If docs/BUILD_RUNBOOK.md does NOT exist: run BOOTSTRAP (section below or in
   docs/BOOTSTRAP_CLAUDE.md).
2. Otherwise: read docs/BUILD_RUNBOOK.md, docs/SPEC.md and docs/PROGRESS.md,
   run the full test suite to confirm the repo is green (fix it first if not),
   then resume from "Current task" in PROGRESS.md using the Execution Protocol
   (runbook section 2) in FULL-AUTO mode.

### FULL-AUTO mode = AUTONOMOUS mode + these overrides
- S1, S4, S5, S6 and S8 are CHECKPOINTS, not stops: write the summary / plan /
  report to docs/PROGRESS.md under "Checkpoints for the human" and continue.
- S2 and S3 are replaced by the one-time PREFLIGHT below.
- T1.1: CLAUDE.md and docs/SPEC.md already exist (created by BOOTSTRAP). Do not
  recreate them; only do the restate / Mermaid / risks part.
- T1.2: never overwrite an existing backend/.env; only create .env.example files.
- S5 (real Gemini run): run it automatically once, capped at 60 Gemini calls,
  and log tokens and estimated cost.
- The ONLY reasons to stop and wait for the human:
  a) PREFLIGHT finds the key rejected or gh not logged in,
  b) S7 deployment (needs the human's Render and Vercel accounts),
  c) the same failure survives 2 fix attempts,
  d) a destructive action, a new paid service, or a change to a locked rule.
- Never ask "should I continue?" between tasks or phases.
- Context management: when your context is getting long, finish the current
  task, commit, update "Current task" and "Next step" in PROGRESS.md, then
  say exactly: "Checkpoint saved. Type /clear, then type go." That is all the
  human needs to type.
- Permission prompts: if Claude Code asks for permission, tell the human once
  to choose the "don't ask again" option for routine commands (tests, npm, git).

### PREFLIGHT (once, right after BOOTSTRAP)
Project root must be /Users/divyanshusrivastava/ChurnLens. Run `pwd`; if it differs, stop and tell the
human to start Claude Code from that folder.
1. Check: python3.11, node >= 20, git, gh. If Homebrew is available, install
   anything missing with brew (python@3.11 node gh libomp). Report versions.
2. backend/.env already exists (written by BOOTSTRAP) with GEMINI_API_KEY set.
   Never print, log, commit or echo its value.
3. Pick the Gemini models automatically: with a small Python script that
   reads the key from backend/.env, call the Gemini API models list endpoint
   (https://generativelanguage.googleapis.com/v1beta/models, key sent in the
   x-goog-api-key header, never in the URL or logs). Choose the newest STABLE
   (non-preview, non-experimental) model whose name contains "pro" for
   GEMINI_MODEL and "flash" for GEMINI_MODEL_FAST; both must support
   generateContent. Write them into backend/.env with the script and report
   the two model names (not the key). If the call fails with 400/401/403,
   stop and tell the human the key was rejected and to create a new key in
   Google AI Studio and put it in backend/.env.
4. Run `gh auth status`. Only if it is NOT logged in, ask the human to run
   `gh auth login` in a terminal and type done. Otherwise do not stop.
5. Safety check before EVERY commit (make it scripts/check_secrets.py and
   run it): `git check-ignore -q backend/.env` must succeed, and a search of
   all tracked and staged files for the actual key value (read from
   backend/.env at runtime, never written anywhere) must find nothing. The
   script prints only PASS or FAIL with file names. On FAIL, stop and fix
   before committing.

### Where things are
- Build plan: docs/BUILD_RUNBOOK.md (tasks, Execution Protocol, stops)
- What to build: docs/SPEC.md
- Where you are: docs/PROGRESS.md
- Sample data: backend/sample_data/ (regenerate with scripts/*.py; fixed seeds)
=====END FILE: CLAUDE.md=====

=====BEGIN FILE: docs/BUILD_RUNBOOK.md=====
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
=====END FILE: docs/BUILD_RUNBOOK.md=====

=====BEGIN FILE: docs/SPEC.md=====
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

=====END FILE: docs/SPEC.md=====

=====BEGIN FILE: docs/PROGRESS.md=====
# ChurnLens progress

Project root: /Users/divyanshusrivastava/ChurnLens

## Current task
T1.1 (after BOOTSTRAP and PREFLIGHT)

## Next step
Run BOOTSTRAP step 5 (sample data), then T1.1.

## Done
- Bootstrap: plan, spec, rules, settings, data generators and backend/.env unpacked.

## Decisions
- Mode: FULL-AUTO (see CLAUDE.md AUTOPILOT).
- Gemini models are auto-selected in PREFLIGHT (newest stable Pro + Flash).
- Sample data is synthetic and IBM-Telco-style (fixed seed 20260331); India
  4-table demo dataset (fixed seed 20260401).

## Checkpoints for the human
(summaries from S1, S4, S5, S6, S8 go here)

## Known issues

## Human actions needed
- Only if asked: `gh auth login`.
- S7 at the end: Render + Vercel dashboard steps (paste GEMINI_API_KEY into Render yourself).
=====END FILE: docs/PROGRESS.md=====

=====BEGIN FILE: docs/DATA_DICTIONARY_INDIA.md=====
# ChurnLens India dataset: data dictionary

A synthetic Indian telecom base of 7,000 customers across 22 telecom circles, about 83% prepaid and 17% postpaid, in four linked tables. Currency is Indian rupees (Rs). All data is synthetic, generated by `scripts/generate_india_sample.py` with a fixed seed (20260401; override with env SEED).

**Timeline:** features are observed up to the **snapshot date, 31 Mar 2026**. Churn is measured in the **90 days after it (1 Apr to 29 Jun 2026)**. Usage history covers Apr 2025 to Mar 2026.

**Churn definition:** prepaid customers churn when they make no recharge for 90 days after pack expiry, or port out. Postpaid customers churn on disconnection or port-out.

## Tables

| File | Grain | Rows (approx.) | Join key |
| --- | --- | --- | --- |
| customers.csv | 1 row per customer (plus 12 duplicate rows) | 7,012 | CustomerID |
| monthly_usage.csv | customer × month, 12 months (fewer for new customers) | ~77,000 | CustomerID + Month |
| care_interactions.csv | 1 row per care contact | ~20,000 | CustomerID |
| offer_history.csv | 1 row per customer per campaign | ~2,300 | CustomerID + Campaign |

Aggregates in customers.csv are computed from the other three tables, so they reconcile.

## customers.csv

### Profile and account
| Column | Description |
| --- | --- |
| CustomerID | Unique ID (exclude from models) |
| SnapshotDate | 2026-03-31 |
| Circle, Zone | Telecom circle (22) and zone |
| Pincode | 6-digit area code (prefix matches circle); use for area-level network mapping, not as a model feature |
| UrbanRural | Urban / Semi-urban / Rural |
| Gender, Age | Demographics |
| PlanType | Prepaid / Postpaid |
| AcquisitionChannel | Retail store, Online, Distributor/retailer, MNP port-in, Telesales |
| ActivationDate, TenureMonths | Start date and months active |
| LockInMonths, ContractEndDate, DaysToContractEnd | Postpaid lock-in (blank if none or prepaid) |
| FamilyPlanMembers, HomeFiber, DTH, ConvergedBundle | Household and multi-product holding |

### Device and network
| Column | Description |
| --- | --- |
| HandsetTier | Budget / Mid / Premium |
| DeviceAgeMonths, Is5GDevice, DualSIM | Handset details |
| SIMSlotRole | Primary / Secondary / Only SIM (secondary SIMs churn most) |
| Our5GCoverage | Whether the customer's area has our 5G |
| AvgDownloadMbps | Measured average speed (40 missing) |
| IndoorCoverageScore | 1 (poor) to 5 (excellent) |
| TowerOutageHours90d | Outage hours at serving sites, last 90 days |

### Usage and money (from monthly_usage.csv, Jan to Mar 2026 vs Oct to Dec 2025)
| Column | Description |
| --- | --- |
| ARPU3mRs, ARPUPrev3mRs, ARPUChangePct | Average revenue per user and its trend |
| Data3mAvgGB, DataPrev3mAvgGB, DataUsageChangePct | Data use and trend |
| Voice3mAvgMin | Voice minutes (6 invalid negative values) |
| ActiveDays3mAvg | Days per month with any usage |
| DroppedCallRate3mPct | Dropped-call rate |
| AppLogins3m | Self-care app logins |
| DaysSinceLastRecharge, LastRechargeRs, PackValidityDays | Prepaid only |
| Recharges90d, AvgRechargeRs3m, AvgRechargeRsPrev3m | Prepaid only |
| RechargeDowntrade | Prepaid: average recharge fell by 15% or more |
| ZeroBalanceDays30d | Prepaid: days with an expired pack in the last 30 days |
| ActiveDiscountPct | Discount already running |
| OverageCharges3mRs, BillShock, OutstandingDuesRs | Postpaid only; bill shock = latest bill over 1.3× average |
| CostToServeMonthlyRs | Estimated network and service cost |
| EstimatedCLVRs | The operator's lifetime-value estimate |

### Competition
| Column | Description |
| --- | --- |
| CompetitorCheapestPlanRs | Cheapest comparable competitor plan in the circle |
| PriceGapPct | Our ARPU vs that plan |
| CompetitorNew5GLaunch90d | A competitor launched 5G in the circle recently |

### Care (from care_interactions.csv, last 90 days)
| Column | Description |
| --- | --- |
| CareContacts90d | All contacts |
| BillingComplaints90d, NetworkComplaints90d, RechargeFailureComplaints90d | Contacts by category (network includes data-speed complaints) |
| RepeatComplaints90d | Same category again within 7 days |
| Escalations90d | Escalated contacts |
| FirstContactResolutionRate | Share resolved on first contact (blank if no contacts) |
| AvgResolutionDays90d | Average days to resolve |
| AvgCareSentiment90d | Sentiment from -1 to +1 |
| PreferredCareChannel | Most-used channel |
| NPS | 0 to 10; blank for about 40% who never answered |

### Offers and consent (from offer_history.csv)
| Column | Description |
| --- | --- |
| MarketingConsent | Yes / No (DND); DND customers are never targeted (TRAI rules) |
| OffersReceived12m | Offers sent across all 3 campaigns (measures offer fatigue) |
| Q1CampaignGroup | Not targeted / Offer sent / Holdout (no offer). Targeting favoured risky customers; 25% of the targeted were randomly held out |
| Q1Offer, Q1OfferChannel, Q1OfferDate | What was sent, how, and when |
| Q1OfferClicked, Q1OfferAccepted, Q1RedemptionDate | Response |
| Q1OfferCostRs | Cost to the operator (0 if not accepted) |

### Outcome
| Column | Description |
| --- | --- |
| Churn | Yes / No (target) |
| ChurnDefinition | Which definition applies to this customer |

### Post-churn columns (leakage: known only at or after churn, never use as features)
| Column | Description |
| --- | --- |
| ChurnDate | Date the customer churned |
| ChurnType | Voluntary (port-out), Voluntary (disconnection), Silent (stopped recharging), Involuntary (non-payment) |
| ChurnReason | Price / value, Network quality, Competitor offer / 5G, Service & care, Using another SIM, Relocation, Non-payment |
| PortOutTo | Competitor A / B / C (port-outs only) |
| PortOutRequestDate | Date of the port-out request |
| ReactivatedWithin60d | Customer won back after churn |

Use these to explain *why* customers left, never to predict *who* will.

## monthly_usage.csv
CustomerID, Month (YYYY-MM), PlanType, ARPU_Rs, DataGB, VoiceMinutes, Recharges and RechargeAmountRs (prepaid), ActiveDays, DroppedCallRatePct, AppLogins. About 0.5% of months are missing on purpose, to mimic data-feed gaps. A prepaid tariff rise in Jan 2026 lifts ARPU by about 3%.

## care_interactions.csv
InteractionID, CustomerID, ContactDate, Category (Billing, Network, Data speed, Recharge failure, Plan change, Device/SIM, Porting query), Channel, Escalated, FirstContactResolved, ResolutionDays, SentimentScore, RepeatWithin7d.

## offer_history.csv
OfferRecordID, CustomerID, Campaign (Q3-FY26, Q4-FY26, Q1-CY26 Retention), Status (Offer sent / Holdout), Offer, Channel, SentDate, ExpiryDate, Clicked, Accepted, RedemptionDate, OfferCostRs. There are 7 offers: 10% loyalty discount, free 10GB data add-on, lock-in renewal with 1 month free, free OTT pack, priority care, 5G handset EMI cashback, and double validity on next recharge.

## Built-in cleaning challenges
- 12 duplicate customer rows
- About 28 Circle values in capitals
- About 21 HandsetTier values with extra spaces
- 40 missing AvgDownloadMbps
- 6 negative Voice3mAvgMin
- Structural blanks (prepaid-only and postpaid-only columns, NPS, no-care customers), which are not errors

## What a good analysis should find
- Secondary SIMs, recharge gaps and downtrading, and approaching lock-in end are the strongest churn signals.
- Churners' ARPU and usage decline for months before they leave.
- Network problems concentrate in rural areas and weaker circles.
- A 5G device without our 5G coverage, in a circle where a competitor just launched 5G, is a high-risk combination.
- The Q1 offers cut churn overall compared with the holdout group, but effects differ by segment. The 5G handset EMI cashback is costly and barely works.
- Naively comparing offer-takers with non-takers is biased; the holdout comparison is the honest one.
=====END FILE: docs/DATA_DICTIONARY_INDIA.md=====

=====BEGIN FILE: docs/DATA_DICTIONARY_TELCO.md=====
# telco_churn.csv: data dictionary

Synthetic telecom churn data for the ChurnLens demo. 7,000 customers (7,014 rows including 14 deliberate duplicate rows), 45 columns, snapshot date 2026-06-30. Churn is measured in the 90 days after the Q1 2026 retention campaign. Generated by `scripts/generate_telco_sample.py` with a fixed seed (20260331; override with env SEED).

## Customer and account

| Column | Type | Description |
| --- | --- | --- |
| customerID | ID | Unique customer ID (exclude from models) |
| gender | Male / Female | Customer gender |
| Age | integer | Age in years (18–85) |
| SeniorCitizen | 0 / 1 | 1 if Age ≥ 60 |
| Partner, Dependents | Yes / No | Household status |
| Region | North / South / East / West / Central | Service region |
| CityTier | Tier 1 / 2 / 3 | City size; Tier 3 has weaker network coverage |
| SignupChannel | Online / Retail store / Telesales / Partner dealer | How the customer joined |
| Contract | Month-to-month / One year / Two year | Contract type |
| tenure | integer | Months with the operator (0 = joined this month) |
| NumLines | integer | Lines on the account |

## Services and billing

| Column | Type | Description |
| --- | --- | --- |
| PhoneService, MultipleLines | Yes / No / No phone service | Voice services |
| InternetService | Fiber optic / DSL / No | Broadband type |
| OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies | Yes / No / No internet service | Add-ons |
| PaperlessBilling | Yes / No | E-bill |
| PaymentMethod | 4 categories | Electronic check, Mailed check, Bank transfer (automatic), Credit card (automatic) |
| MonthlyCharges | currency | Current monthly bill |
| TotalCharges | currency (text) | Lifetime billing; blank for the 11 customers with tenure 0 |

## Usage and experience (last 3 months)

| Column | Type | Description |
| --- | --- | --- |
| AvgMonthlyDataGB | decimal | Average data per month (60 missing values) |
| DataUsageChange3mPct | % | Change in data use vs the previous 3 months |
| AvgMonthlyCallMinutes | integer | Voice minutes per month (5 invalid negative values) |
| DroppedCallRatePct | % | Share of calls dropped |
| NetworkComplaints90d | integer | Network complaints in 90 days |
| SupportTickets90d | integer | Support tickets in 90 days |
| AvgResolutionDays | decimal | Average ticket resolution time; blank if no tickets |
| LatePayments12m | integer | Late payments in 12 months |
| AppLogins30d | integer | Self-care app logins in 30 days |
| PlanDowngrade6m | Yes / No | Moved to a cheaper plan in 6 months |
| NPS | 0–10 | Survey score; blank for ~38% who never answered |

## Retention campaign (Q1 2026)

| Column | Type | Description |
| --- | --- | --- |
| CampaignGroup | Not targeted / Offer sent / Holdout (no offer) | Targeted customers were picked by an old CRM risk score (so they are riskier); 25% of them were randomly held out as a control group |
| OfferShown | 6 offers or blank | 10% loyalty discount (3 mo), Free 10GB data booster, 1 month free on annual plan, Free OTT streaming (6 mo), Priority tech support (6 mo), Device upgrade credit |
| OfferChannel | SMS / App push / Outbound call / Email | Delivery channel |
| OfferDate | date | Date the offer was sent, or the holdout assignment date (always before the churn window) |
| OfferClicked | Yes / No | Opened or clicked the offer |
| OfferAccepted | Yes / No | Redeemed the offer (only possible after a click) |
| OfferCost | currency | Cost to the operator; 0 if not accepted |

## Outcome and metadata

| Column | Type | Description |
| --- | --- | --- |
| Churn | Yes / No | Left within 90 days after the campaign (target) |
| SnapshotDate | date | Extract date |

## Built-in cleaning challenges

- 14 exact duplicate rows
- 11 blank TotalCharges
- About 28 InternetService values in lower case ("fiber optic")
- About 21 PaymentMethod values with extra spaces
- 60 missing AvgMonthlyDataGB
- 5 negative AvgMonthlyCallMinutes
- NPS and AvgResolutionDays blanks that are meaningful, not errors

## Modelling notes

- The campaign columns are treatments, not customer traits. Exclude them from the churn-risk model and analyse them in the offer and A/B phases.
- Offer effects vary by segment, and one offer (device upgrade credit) doesn't reduce churn at all. A good analysis should find both.
=====END FILE: docs/DATA_DICTIONARY_TELCO.md=====

=====BEGIN FILE: .claude/settings.json=====
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)",
      "Bash(pytest:*)",
      "Bash(ruff:*)",
      "Bash(uvicorn:*)",
      "Bash(alembic:*)",
      "Bash(source:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(node:*)",
      "Bash(git init:*)",
      "Bash(git status:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git checkout:*)",
      "Bash(git switch:*)",
      "Bash(git branch:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git push:*)",
      "Bash(git pull:*)",
      "Bash(git merge:*)",
      "Bash(git fetch:*)",
      "Bash(gh auth status:*)",
      "Bash(gh repo create:*)",
      "Bash(gh repo view:*)",
      "Bash(gh pr:*)",
      "Bash(gh run:*)",
      "Bash(docker build:*)",
      "Bash(docker run:*)",
      "Bash(curl -s http://localhost:*)",
      "Bash(ls:*)",
      "Bash(mkdir:*)",
      "Bash(cat:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(wc:*)",
      "Bash(grep:*)",
      "Bash(brew install:*)",
      "Bash(brew list:*)"
    ],
    "deny": [
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git reset --hard:*)",
      "Bash(git clean:*)",
      "Bash(rm -rf:*)",
      "Bash(sudo:*)",
      "Read(./backend/.env)",
      "Read(./frontend/.env.local)",
      "Read(./.env)"
    ]
  }
}
=====END FILE: .claude/settings.json=====

=====BEGIN FILE: .gitignore=====
.env
.env.*
!.env.example
**/.venv/
node_modules/
.next/
.vercel/
data/
*.db
__pycache__/
backend/sample_data/india/
.claude/settings.local.json
=====END FILE: .gitignore=====

=====BEGIN FILE: scripts/generate_telco_sample.py=====
"""
Synthetic telecom churn dataset with retention offers (ChurnLens demo data).
Fixed default seed (override with env SEED) so tests are reproducible.
Churn and offer uptake follow realistic, noisy relationships so there is signal to find.
"""
import numpy as np, pandas as pd, secrets, string
import os, sys
SEED = int(os.environ.get("SEED", "20260331"))
rng = np.random.default_rng(SEED)
N = 7000
SNAPSHOT = pd.Timestamp("2026-06-30")
ch = lambda opts, p, n=N: rng.choice(opts, size=n, p=p)
yes = lambda s: (s == "Yes").astype(float)

d = pd.DataFrame()
ids = set()
while len(ids) < N:
    ids.add(f"{rng.integers(1000,9999)}-{''.join(rng.choice(list(string.ascii_uppercase),5))}")
d["customerID"] = list(rng.permutation(sorted(ids)))

# ---- demographics & account ----
d["gender"] = ch(["Male","Female"], [0.5,0.5])
age = np.clip(np.round(rng.gamma(9, 4.6, N) + rng.normal(0,3,N)), 18, 85).astype(int)
d["Age"] = age
d["SeniorCitizen"] = (age >= 60).astype(int)
d["Partner"] = np.where(rng.random(N) < np.clip(0.2 + (age-18)/80, 0.15, 0.75), "Yes", "No")
d["Dependents"] = np.where(d.Partner.eq("Yes"), ch(["Yes","No"],[0.52,0.48]), ch(["Yes","No"],[0.1,0.9]))
d["Region"] = ch(["North","South","East","West","Central"], [0.24,0.27,0.14,0.23,0.12])
d["CityTier"] = ch(["Tier 1","Tier 2","Tier 3"], [0.45,0.35,0.20])
d["SignupChannel"] = ch(["Online","Retail store","Telesales","Partner dealer"], [0.38,0.34,0.14,0.14])
contract = ch(["Month-to-month","One year","Two year"], [0.55,0.21,0.24])
d["Contract"] = contract
scale = pd.Series(contract).map({"Month-to-month":9,"One year":20,"Two year":30}).values
ten = np.clip(np.round(rng.gamma(2.0, scale) + rng.normal(0,3,N)), 1, 72).astype(int)
zero_idx = rng.choice(np.where(contract != "Month-to-month")[0], 11, replace=False)
ten[zero_idx] = 0
d["tenure"] = ten
d["NumLines"] = rng.choice([1,2,3,4], N, p=[0.62,0.22,0.11,0.05]) + (d.Dependents.eq("Yes") & (rng.random(N)<0.3)).astype(int)

# ---- services ----
d["PhoneService"] = ch(["Yes","No"], [0.9,0.1])
d["MultipleLines"] = np.where(d.PhoneService.eq("No"), "No phone service", np.where(d.NumLines>1, "Yes", ch(["Yes","No"],[0.25,0.75])))
net = np.where(d.CityTier.eq("Tier 3"), ch(["Fiber optic","DSL","No"],[0.25,0.40,0.35]), ch(["Fiber optic","DSL","No"],[0.49,0.33,0.18]))
d["InternetService"] = net
no_net = d.InternetService.eq("No")
for col,p in [("OnlineSecurity",0.37),("OnlineBackup",0.44),("DeviceProtection",0.44),("TechSupport",0.37),("StreamingTV",0.49),("StreamingMovies",0.50)]:
    d[col] = np.where(no_net, "No internet service", np.where(rng.random(N) < p, "Yes", "No"))
d["PaperlessBilling"] = np.where(rng.random(N) < np.where(age<40,0.72,0.48), "Yes", "No")
d["PaymentMethod"] = ch(["Electronic check","Mailed check","Bank transfer (automatic)","Credit card (automatic)"], [0.34,0.23,0.22,0.21])

# ---- charges ----
mc = 20 + np.where(d.PhoneService.eq("Yes"), rng.normal(5,1.5,N), 0) + np.where(d.MultipleLines.eq("Yes"), rng.normal(5,1.5,N)*np.minimum(d.NumLines,3)/1.5, 0)
mc += np.select([d.InternetService.eq("Fiber optic"), d.InternetService.eq("DSL")], [rng.normal(45,5,N), rng.normal(25,4,N)], 0)
for col in ["OnlineSecurity","OnlineBackup","DeviceProtection","TechSupport","StreamingTV","StreamingMovies"]:
    mc += np.where(d[col].eq("Yes"), rng.normal(7,2,N), 0)
d["MonthlyCharges"] = np.round(np.clip(mc + rng.normal(0,3,N), 18.25, 139.0), 2)
tc = np.maximum(d.MonthlyCharges * d.tenure * rng.normal(1.0,0.04,N), d.MonthlyCharges)
d["TotalCharges"] = np.round(tc,2).astype(str)
d.loc[d.tenure.eq(0), "TotalCharges"] = " "

# ---- usage & experience (last 3 months) ----
heavy = np.where(d.InternetService.eq("Fiber optic"), 1.6, np.where(d.InternetService.eq("DSL"), 1.0, 0.0))
data_gb = np.round(rng.gamma(2.2, 9, N) * heavy * np.where(age<35,1.4,1.0), 1)
d["AvgMonthlyDataGB"] = data_gb
latent_disengage = rng.normal(0,1,N)          # hidden dissatisfaction driver
drop = np.clip(np.round(rng.normal(-3 - 9*latent_disengage.clip(0), 12, N), 1), -95, 80)
d["DataUsageChange3mPct"] = np.where(no_net, 0.0, drop)
d["AvgMonthlyCallMinutes"] = np.round(np.clip(rng.gamma(2.5, 120, N) * np.where(d.PhoneService.eq("Yes"),1,0) * (1 - 0.1*latent_disengage.clip(0)), 0, None)).astype(int)
dcr = np.round(np.clip(rng.gamma(2, 0.9, N) + np.where(d.CityTier.eq("Tier 3"),1.2,0) + np.where(d.Region.eq("East"),0.6,0), 0, 15), 2)
d["DroppedCallRatePct"] = dcr
d["NetworkComplaints90d"] = rng.poisson(0.15 + 0.25*dcr/2)
tickets = rng.poisson(np.clip(0.4 + 0.5*latent_disengage.clip(0) + 0.3*d.InternetService.eq("Fiber optic") + 0.15*dcr, 0.05, None))
d["SupportTickets90d"] = tickets
d["AvgResolutionDays"] = np.where(tickets>0, np.round(np.clip(rng.gamma(2, 1.6, N) + np.where(d.TechSupport.eq("Yes"),-1.0,0.5), 0.2, 21),1), np.nan)
d["LatePayments12m"] = rng.poisson(np.clip(0.3 + 0.8*d.PaymentMethod.isin(["Electronic check","Mailed check"]) + 0.4*latent_disengage.clip(0), 0.05, None))
d["AppLogins30d"] = rng.poisson(np.clip((6 + 8*(age<40)) * np.exp(-0.35*latent_disengage.clip(0)), 0.2, None))
d["PlanDowngrade6m"] = np.where(rng.random(N) < 0.05 + 0.10*(latent_disengage>1), "Yes", "No")
nps = np.clip(np.round(rng.normal(7.2 - 1.3*latent_disengage.clip(0) - 0.25*d.SupportTickets90d - 0.2*dcr, 1.8)), 0, 10)
d["NPS"] = np.where(rng.random(N) < 0.38, np.nan, nps)   # ~38% never answered the survey

# ---- churn propensity before any offer (the "true" risk) ----
z0 = (-1.85
      + np.select([d.Contract.eq("Month-to-month"), d.Contract.eq("One year")], [1.25, 0.0], -1.35)
      - 0.03*d.tenure
      + 0.7*d.InternetService.eq("Fiber optic") - 0.8*no_net
      + 0.4*d.PaymentMethod.eq("Electronic check")
      - 0.4*yes(d.OnlineSecurity) - 0.35*yes(d.TechSupport)
      + 0.2*yes(d.PaperlessBilling) + 0.2*d.SeniorCitizen - 0.15*yes(d.Dependents)
      + 0.010*(d.MonthlyCharges-65)
      - 0.012*d.DataUsageChange3mPct.clip(-60,30)
      + 0.18*d.SupportTickets90d + 0.25*d.NetworkComplaints90d
      + 0.06*dcr + 0.12*d.LatePayments12m
      - 0.04*d.AppLogins30d.clip(0,20)
      + 0.5*yes(d.PlanDowngrade6m) - 0.12*(d.NumLines-1)
      + 0.55*latent_disengage.clip(0)
      + rng.normal(0,0.6,N))

# ---- retention campaign (Q1 2026) ----
# the operator's old CRM score targets riskier customers (selection bias), plus randomness
crm_score = 1/(1+np.exp(-(z0 + rng.normal(0,0.9,N))))
targeted = rng.random(N) < np.clip(0.08 + 0.75*crm_score, 0, 0.9)
targeted &= d.tenure.values > 0
holdout = targeted & (rng.random(N) < 0.25)            # random control group, no offer
offered = targeted & ~holdout

offers = {
  "10% loyalty discount (3 mo)":   dict(cost=lambda mc: 0.30*mc, w=0.26),
  "Free 10GB data booster":         dict(cost=lambda mc: 6.0+0*mc, w=0.20),
  "1 month free on annual plan":    dict(cost=lambda mc: 1.0*mc, w=0.18),
  "Free OTT streaming (6 mo)":      dict(cost=lambda mc: 18.0+0*mc, w=0.16),
  "Priority tech support (6 mo)":   dict(cost=lambda mc: 5.0+0*mc, w=0.12),
  "Device upgrade credit":          dict(cost=lambda mc: 45.0+0*mc, w=0.08),
}
names = list(offers); w = np.array([offers[k]["w"] for k in names]); w/=w.sum()
offer = np.full(N, "", dtype=object)
offer[offered] = rng.choice(names, offered.sum(), p=w)
d["CampaignGroup"] = np.where(offered, "Offer sent", np.where(holdout, "Holdout (no offer)", "Not targeted"))
d["OfferShown"] = offer
d["OfferChannel"] = np.where(offered, ch(["SMS","App push","Outbound call","Email"],[0.40,0.25,0.20,0.15]), "")
start, end = pd.Timestamp("2026-01-05"), pd.Timestamp("2026-03-27")
days = rng.integers(0, (end-start).days+1, N)
d["OfferDate"] = np.where(targeted, (start + pd.to_timedelta(days, unit="D")).strftime("%Y-%m-%d"), "")

mcv = d.MonthlyCharges.values
streamer = (yes(d.StreamingTV)+yes(d.StreamingMovies)).values > 0
heavy_user = d.AvgMonthlyDataGB.values > np.nanpercentile(d.AvgMonthlyDataGB[d.AvgMonthlyDataGB>0], 60)
mtm = (d.Contract=="Month-to-month").values
many_tickets = d.SupportTickets90d.values >= 2
# relevance drives click & accept
rel = np.zeros(N)
for i_name in names:
    m = offer == i_name
    if i_name.startswith("10%"): rel[m] = 0.5 + 0.5*(mcv[m] > 75)
    elif "data booster" in i_name: rel[m] = 0.2 + 0.8*heavy_user[m]
    elif "annual" in i_name: rel[m] = 0.2 + 0.6*mtm[m]
    elif "OTT" in i_name: rel[m] = 0.2 + 0.7*streamer[m]
    elif "Priority" in i_name: rel[m] = 0.2 + 0.7*many_tickets[m]
    else: rel[m] = 0.35
chan_boost = pd.Series(d.OfferChannel).map({"SMS":0.0,"App push":0.3,"Outbound call":0.6,"Email":-0.3,"":0}).values
p_click = 1/(1+np.exp(-(-1.3 + 2.2*rel + chan_boost + 0.03*d.AppLogins30d.clip(0,20).values + rng.normal(0,0.5,N))))
clicked = offered & (rng.random(N) < p_click)
p_acc = 1/(1+np.exp(-(-0.9 + 1.8*rel + 0.3*chan_boost + rng.normal(0,0.5,N))))
accepted = clicked & (rng.random(N) < p_acc)
d["OfferClicked"] = np.where(offered, np.where(clicked,"Yes","No"), "")
d["OfferAccepted"] = np.where(offered, np.where(accepted,"Yes","No"), "")
cost = np.zeros(N)
for k in names:
    m = accepted & (offer == k)
    cost[m] = offers[k]["cost"](mcv[m])
d["OfferCost"] = np.where(offered, np.where(accepted, np.round(cost,2).astype(str), "0"), "")

# ---- true offer effect on churn (heterogeneous, only if accepted) ----
eff = np.zeros(N)
for k in names:
    m = accepted & (offer == k)
    if k.startswith("10%"): eff[m] = -0.55 - 0.60*(mcv[m] > 75)
    elif "data booster" in k: eff[m] = -0.20 - 0.95*heavy_user[m]
    elif "annual" in k: eff[m] = -0.45 - 1.00*mtm[m]
    elif "OTT" in k: eff[m] = -0.10 - 0.85*streamer[m]
    elif "Priority" in k: eff[m] = -0.20 - 0.95*many_tickets[m]
    else: eff[m] = -0.10
eff[accepted] += rng.normal(0, 0.25, accepted.sum())      # individual variation
z = z0 + eff
churn = (rng.random(N) < 1/(1+np.exp(-z))) & (d.tenure.values > 0)
d["Churn"] = np.where(churn, "Yes", "No")

# ---- light real-world messiness for the cleaning step ----
def mess(col, frac, fn):
    idx = rng.choice(N, int(frac*N), replace=False); d.loc[idx, col] = d.loc[idx, col].map(fn)
mess("InternetService", 0.004, lambda s: s.lower() if s!="No" else s)
mess("PaymentMethod", 0.003, lambda s: " "+s+" ")
nan_idx = rng.choice(np.where(~no_net)[0], 60, replace=False); d.loc[nan_idx, "AvgMonthlyDataGB"] = np.nan
neg_idx = rng.choice(np.where(d.AvgMonthlyCallMinutes>0)[0], 5, replace=False); d.loc[neg_idx, "AvgMonthlyCallMinutes"] *= -1
dups = d[d.tenure>0].sample(14, random_state=int(rng.integers(1e9)))
d = pd.concat([d, dups]).sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)

d["SnapshotDate"] = SNAPSHOT.strftime("%Y-%m-%d")
out = sys.argv[1] if len(sys.argv) > 1 else "backend/sample_data/telco_churn.csv"
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
d.to_csv(out, index=False)
print("seed", SEED, "rows", len(d))
=====END FILE: scripts/generate_telco_sample.py=====

=====BEGIN FILE: scripts/generate_india_sample.py=====
"""
ChurnLens India demo dataset (synthetic). Fixed default seed (override with env SEED).
Outputs (in ./churnlens_india_dataset/):
  customers.csv          one row per customer: profile, device, network, money, care & offer
                         aggregates, and churn outcome (+ post-churn reason columns)
  monthly_usage.csv      12 months of history per customer (Apr 2025 - Mar 2026)
  care_interactions.csv  every care contact in the 12 months
  offer_history.csv      every retention offer across 3 campaigns
Timeline: features observed up to SNAPSHOT (2026-03-31); churn measured 2026-04-01..2026-06-29 (90 days).
"""
import numpy as np, pandas as pd, secrets, string, os
import sys
SEED = int(os.environ.get("SEED", "20260401")); rng = np.random.default_rng(SEED)
N = 7000
SNAP = pd.Timestamp("2026-03-31"); WIN_END = SNAP + pd.Timedelta(days=90)
MONTHS = pd.period_range("2025-04", "2026-03", freq="M")
OUT = sys.argv[1] if len(sys.argv) > 1 else "backend/sample_data/india"; os.makedirs(OUT, exist_ok=True)
ch = lambda o, p, n=N: rng.choice(o, size=n, p=np.array(p)/np.sum(p))
sig = lambda x: 1/(1+np.exp(-x))

# ---------------- customer master ----------------
ids = set()
while len(ids) < N: ids.add("C" + "".join(rng.choice(list(string.digits), 7)))
c = pd.DataFrame({"CustomerID": sorted(ids)}); c = c.sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)
circles = {  # circle: (weight, pincode first digits, zone)
 "Delhi":(7,"11","North"),"Mumbai":(6,"40","West"),"Kolkata":(4,"70","East"),"Maharashtra & Goa":(8,"41","West"),
 "Karnataka":(7,"56","South"),"Tamil Nadu":(7,"60","South"),"Kerala":(4,"68","South"),"Andhra Pradesh & Telangana":(8,"50","South"),
 "Gujarat":(6,"38","West"),"Rajasthan":(5,"30","North"),"UP East":(8,"22","North"),"UP West":(6,"24","North"),
 "Bihar & Jharkhand":(7,"80","East"),"West Bengal":(5,"71","East"),"Madhya Pradesh & Chhattisgarh":(6,"45","Central"),
 "Punjab":(3,"14","North"),"Haryana":(3,"12","North"),"Odisha":(3,"75","East"),"Assam":(2,"78","North East"),
 "North East":(1,"79","North East"),"Himachal Pradesh":(1,"17","North"),"Jammu & Kashmir":(1,"18","North")}
cn = list(circles); cw = [circles[k][0] for k in cn]
c["Circle"] = ch(cn, cw)
c["Zone"] = c.Circle.map({k:v[2] for k,v in circles.items()})
c["Pincode"] = [circles[x][1] + f"{rng.integers(0,10000):04d}" for x in c.Circle]
metro = c.Circle.isin(["Delhi","Mumbai","Kolkata"])
c["UrbanRural"] = np.where(metro, ch(["Urban","Semi-urban"],[0.9,0.1]), ch(["Urban","Semi-urban","Rural"],[0.35,0.30,0.35]))
rural = (c.UrbanRural=="Rural").values
c["Gender"] = ch(["Male","Female"],[0.58,0.42])
age = np.clip(np.round(rng.gamma(7.5, 4.6, N)+ rng.normal(0,3,N)), 18, 80).astype(int); c["Age"] = age
c["PlanType"] = np.where(rng.random(N) < np.where(metro,0.30,0.14), "Postpaid", "Prepaid")
post = (c.PlanType=="Postpaid").values; pre = ~post
c["AcquisitionChannel"] = ch(["Retail store","Online","Distributor/retailer","MNP port-in","Telesales"],[0.34,0.18,0.30,0.12,0.06])
ten = np.clip(np.round(rng.gamma(1.6, 22, N)), 1, 180).astype(int)
c["TenureMonths"] = ten
c["ActivationDate"] = (SNAP - pd.to_timedelta(ten*30.4 + rng.integers(0,30,N), unit="D")).strftime("%Y-%m-%d")
lock = np.where(post & (rng.random(N)<0.55), rng.choice([12,24],N,p=[0.6,0.4]), 0)
cycle_end = np.where(lock>0, lock*np.ceil((ten+0.5)/np.maximum(lock,1)), np.nan)
days_to_end = np.where(lock>0, np.round((cycle_end - ten)*30.4 - rng.integers(0,30,N)), np.nan)
days_to_end = np.where(lock>0, np.maximum(days_to_end, 1), np.nan)
c["LockInMonths"] = np.where(post, lock, np.nan)
c["ContractEndDate"] = [ (SNAP + pd.Timedelta(days=int(x))).strftime("%Y-%m-%d") if not np.isnan(x) else "" for x in days_to_end]
c["DaysToContractEnd"] = days_to_end

# household / convergence
c["FamilyPlanMembers"] = np.where(post, rng.choice([1,2,3,4],N,p=[0.55,0.22,0.15,0.08]), 1)
c["HomeFiber"] = np.where(rng.random(N) < np.where(rural,0.03,0.16) + 0.12*post, "Yes","No")
c["DTH"] = np.where(rng.random(N) < 0.18 + 0.10*(c.HomeFiber=="Yes"), "Yes","No")
c["ConvergedBundle"] = np.where((c.HomeFiber=="Yes") & (rng.random(N)<0.55), "Yes","No")

# device
tier = np.where(rng.random(N) < 0.20+0.25*post, "Premium", np.where(rng.random(N)<0.55,"Mid","Budget"))
c["HandsetTier"] = tier
c["DeviceAgeMonths"] = np.clip(np.round(rng.gamma(2.2, 11, N)),0,96).astype(int)
p5g = np.select([tier=="Premium", tier=="Mid"], [0.92,0.62], 0.28) * np.where(c.DeviceAgeMonths>36,0.35,1)
c["Is5GDevice"] = np.where(rng.random(N)<p5g,"Yes","No")
c["DualSIM"] = np.where(rng.random(N) < 0.88, "Yes","No")
secondary = (c.DualSIM=="Yes").values & (rng.random(N) < np.where(pre, 0.34, 0.10))
c["SIMSlotRole"] = np.where(c.DualSIM=="No","Only SIM", np.where(secondary,"Secondary","Primary"))

# network (area level + noise)
circle_q = {k: rng.normal(0,0.6) for k in cn}
netq = np.array([circle_q[x] for x in c.Circle]) - 0.9*rural + 0.3*metro + rng.normal(0,0.6,N)   # higher = better
c["Our5GCoverage"] = np.where(rng.random(N) < sig(0.8 + 1.2*netq - 1.5*rural), "Yes","No")
c["AvgDownloadMbps"] = np.round(np.clip(np.exp(2.7 + 0.35*netq + 0.9*(c.Our5GCoverage=="Yes")*(c.Is5GDevice=="Yes") + rng.normal(0,0.35,N)), 1, 400),1)
c["IndoorCoverageScore"] = np.clip(np.round(3.2 + 0.8*netq + rng.normal(0,0.7,N)),1,5).astype(int)
c["TowerOutageHours90d"] = np.round(np.clip(rng.gamma(1.5, 3, N)*np.exp(-0.5*netq),0,200),1)

# competition (circle level)
comp_price = {k: rng.choice([199,209,239,249,299]) for k in cn}
comp5g = {k: rng.random()<0.6 for k in cn}
c["CompetitorCheapestPlanRs"] = c.Circle.map(comp_price)
c["CompetitorNew5GLaunch90d"] = np.where(c.Circle.map(comp5g), "Yes","No")

# consent
c["MarketingConsent"] = np.where(rng.random(N) < 0.82, "Yes","No (DND)")

# hidden drivers
unhappy = rng.normal(0,1,N)            # latent dissatisfaction
price_sens = rng.normal(0,1,N) + 0.4*pre - 0.3*(tier=="Premium")

# ---------------- monthly usage panel ----------------
base_arpu = np.where(post, rng.normal(620,180,N)*c.FamilyPlanMembers.values**0.6, rng.normal(245,70,N))
base_arpu = np.clip(base_arpu, 99, 3500)
base_data = np.clip(rng.gamma(2.2, 7, N) * (1.4 if True else 1) * np.where(age<30,1.5,1) * np.where(secondary,0.35,1), 0.2, 250)
base_voice = np.clip(rng.gamma(2.5, 180, N) * np.where(secondary,0.4,1), 5, 4000)
# trend over last months driven by latent unhappiness & price sensitivity
decline = 0.012*np.clip(unhappy,0,None) + 0.006*np.clip(price_sens,0,None) + rng.normal(0,0.01,N)
rows = []
m_idx = np.arange(12)
active_from = np.maximum(0, 12 - ten)              # months before activation are absent
for k, per in enumerate(MONTHS):
    alive = k >= active_from
    f = np.exp(-decline*np.maximum(0, k-6)*1.6) * (1 + rng.normal(0,0.07,N))
    arpu = np.round(base_arpu*f*(1 + 0.03*(k>=9)*pre), 0)           # small tariff hike in Jan-26 for prepaid
    data = np.round(base_data*f*(1+0.02*k)*(1+rng.normal(0,0.1,N)),2)
    voice = np.round(base_voice*f*(1+rng.normal(0,0.08,N)))
    rec_cnt = np.where(pre, rng.poisson(np.clip(1.1*f,0.05,None)), np.nan)
    rec_amt = np.where(pre, np.round(arpu*np.where(rec_cnt>0,1,0)), np.nan)
    days_active = np.clip(np.round(30*np.clip(f,0,1) - rng.poisson(1+2*np.clip(unhappy,0,None)*(k>=9))),0,31)
    dcr = np.round(np.clip(rng.gamma(2,0.6,N)*np.exp(-0.45*netq),0,20),2)
    logins = rng.poisson(np.clip((4+6*(age<35))*f,0.1,None))
    rows.append(pd.DataFrame({"CustomerID":c.CustomerID,"Month":str(per),"PlanType":c.PlanType,"ARPU_Rs":arpu,
        "DataGB":data,"VoiceMinutes":voice,"Recharges":rec_cnt,"RechargeAmountRs":rec_amt,"ActiveDays":days_active,
        "DroppedCallRatePct":dcr,"AppLogins":logins})[alive])
mu = pd.concat(rows, ignore_index=True)
# data gaps: ~0.5% months missing
mu = mu.drop(mu.sample(frac=0.005, random_state=int(rng.integers(1e9))).index).reset_index(drop=True)

g = mu.groupby("CustomerID")
last3 = mu[mu.Month>="2026-01"].groupby("CustomerID"); prev3 = mu[(mu.Month>="2025-10")&(mu.Month<"2026-01")].groupby("CustomerID")
agg = pd.DataFrame({
 "ARPU3mRs": last3.ARPU_Rs.mean(), "ARPUPrev3mRs": prev3.ARPU_Rs.mean(),
 "Data3mAvgGB": last3.DataGB.mean(), "DataPrev3mAvgGB": prev3.DataGB.mean(),
 "Voice3mAvgMin": last3.VoiceMinutes.mean(), "ActiveDays3mAvg": last3.ActiveDays.mean(),
 "DroppedCallRate3mPct": last3.DroppedCallRatePct.mean(), "AppLogins3m": last3.AppLogins.sum(),
 "Recharges90d": last3.Recharges.sum(min_count=1), "AvgRechargeRs3m": last3.RechargeAmountRs.mean(),
 "AvgRechargeRsPrev3m": prev3.RechargeAmountRs.mean()})
c = c.merge(agg, left_on="CustomerID", right_index=True, how="left")
c["ARPUChangePct"] = np.round(100*(c.ARPU3mRs/c.ARPUPrev3mRs - 1),1)
c["DataUsageChangePct"] = np.round(100*(c.Data3mAvgGB/c.DataPrev3mAvgGB - 1),1)
for col in ["ARPU3mRs","ARPUPrev3mRs","Data3mAvgGB","DataPrev3mAvgGB","Voice3mAvgMin","ActiveDays3mAvg","DroppedCallRate3mPct","AvgRechargeRs3m","AvgRechargeRsPrev3m"]:
    c[col] = c[col].round(1)
c["RechargeDowntrade"] = np.where(pre, np.where(c.AvgRechargeRs3m < 0.85*c.AvgRechargeRsPrev3m, "Yes","No"), "")
dslr = np.where(pre, np.clip(np.round(rng.gamma(1.3, 9, N)*(1+1.5*np.clip(unhappy,0,None))*np.where(secondary,1.8,1)),0,120), np.nan)
c["DaysSinceLastRecharge"] = dslr
validity = np.where(pre, rng.choice([28,56,84,365],N,p=[0.55,0.2,0.2,0.05]), np.nan)
c["PackValidityDays"] = validity
c["LastRechargeRs"] = np.where(pre, np.round(c.AvgRechargeRs3m.fillna(199)*rng.normal(1,0.12,N)), np.nan)
c["ZeroBalanceDays30d"] = np.where(pre, np.clip(np.round(np.maximum(0, dslr - validity + 30) * (rng.random(N)<0.6)),0,30), np.nan)
c["ActiveDiscountPct"] = np.where(rng.random(N)<0.12, rng.choice([5,10,15,20],N), 0)
c["OverageCharges3mRs"] = np.where(post, np.round(np.clip(rng.gamma(0.6, 90, N)*(rng.random(N)<0.4),0,None)), np.nan)
last_bill = c.ARPU3mRs*np.where(post, 1 + np.clip(rng.gamma(0.8,0.12,N),0,1.2), 1)
c["BillShock"] = np.where(post, np.where(last_bill > 1.3*c.ARPU3mRs, "Yes","No"), "")
dues = np.where(post, np.round(np.where(rng.random(N) < 0.10 + 0.08*np.clip(price_sens,0,None), rng.gamma(1.5,400,N), 0)), np.nan)
c["OutstandingDuesRs"] = dues
c["CostToServeMonthlyRs"] = np.round(np.clip(60 + 0.9*c.Data3mAvgGB.fillna(0) + 0.02*c.Voice3mAvgMin.fillna(0) + rng.normal(0,15,N), 30, None))
c["PriceGapPct"] = np.round(100*(c.ARPU3mRs/c.CompetitorCheapestPlanRs - 1),1)

# ---------------- care interactions log ----------------
rate = np.clip(0.07 + 0.16*np.clip(unhappy,0,None) + 0.09*np.exp(-0.4*netq) + 0.08*post, 0.02, None)  # per month
cats = ["Billing","Network","Recharge failure","Data speed","Plan change","Device/SIM","Porting query"]
care = []
for k, per in enumerate(MONTHS):
    n_ev = rng.poisson(rate)
    n_ev[k < active_from] = 0
    idx = np.repeat(np.arange(N), n_ev)
    if len(idx)==0: continue
    net_w = np.exp(-0.6*netq[idx]); bill_w = np.where(post[idx], 1.6, 0.4)*(1+0.5*np.clip(price_sens[idx],0,None))
    w = np.stack([bill_w, 1.2*net_w, np.where(pre[idx],0.9,0.05), 0.9*net_w, np.full(len(idx),0.5), np.full(len(idx),0.35),
                  0.05 + 0.25*(np.clip(unhappy[idx],0,None)>1)*(k>=9)], axis=1)
    w = w/w.sum(1,keepdims=True); cat = np.array([rng.choice(7, p=r) for r in w])
    day = rng.integers(1, per.days_in_month+1, len(idx))
    chan = rng.choice(["Call centre","App/chat","Store","Social media","Email"], len(idx), p=[0.46,0.28,0.16,0.05,0.05])
    esc = rng.random(len(idx)) < 0.06 + 0.08*np.clip(unhappy[idx],0,None)
    res_days = np.round(np.clip(rng.gamma(1.6, 1.5, len(idx)) * np.where(esc, 3, 1), 0.1, 45), 1)
    fcr = (rng.random(len(idx)) < 0.62 - 0.1*np.clip(unhappy[idx],0,None)) & ~esc
    sentiment = np.clip(np.round(rng.normal(0.1 - 0.35*np.clip(unhappy[idx],0,None) - 0.3*esc, 0.35),2), -1, 1)
    care.append(pd.DataFrame({"CustomerID": c.CustomerID.values[idx],
        "ContactDate": [f"{per}-{d:02d}" for d in day], "Category": np.array(cats)[cat], "Channel": chan,
        "Escalated": np.where(esc,"Yes","No"), "FirstContactResolved": np.where(fcr,"Yes","No"),
        "ResolutionDays": res_days, "SentimentScore": sentiment}))
care = pd.concat(care, ignore_index=True).sort_values(["CustomerID","ContactDate"]).reset_index(drop=True)
care.insert(0, "InteractionID", [f"T{i:07d}" for i in rng.permutation(len(care))])
care["RepeatWithin7d"] = "No"
cd = pd.to_datetime(care.ContactDate)
same = (care.CustomerID == care.CustomerID.shift()) & (care.Category == care.Category.shift()) & ((cd - cd.shift()).dt.days <= 7)
care.loc[same, "RepeatWithin7d"] = "Yes"
r90 = care[pd.to_datetime(care.ContactDate) > SNAP - pd.Timedelta(days=90)]
cg = r90.groupby("CustomerID")
cagg = pd.DataFrame({"CareContacts90d": cg.size(),
  "BillingComplaints90d": cg.Category.apply(lambda s:(s=="Billing").sum()),
  "NetworkComplaints90d": cg.Category.apply(lambda s:s.isin(["Network","Data speed"]).sum()),
  "RechargeFailureComplaints90d": cg.Category.apply(lambda s:(s=="Recharge failure").sum()),
  "RepeatComplaints90d": cg.RepeatWithin7d.apply(lambda s:(s=="Yes").sum()),
  "Escalations90d": cg.Escalated.apply(lambda s:(s=="Yes").sum()),
  "FirstContactResolutionRate": cg.FirstContactResolved.apply(lambda s: round((s=="Yes").mean(),2)),
  "AvgResolutionDays90d": cg.ResolutionDays.mean().round(1),
  "AvgCareSentiment90d": cg.SentimentScore.mean().round(2),
  "PreferredCareChannel": cg.Channel.agg(lambda s: s.value_counts().index[0])})
c = c.merge(cagg, left_on="CustomerID", right_index=True, how="left")
for col in ["CareContacts90d","BillingComplaints90d","NetworkComplaints90d","RechargeFailureComplaints90d","RepeatComplaints90d","Escalations90d"]:
    c[col] = c[col].fillna(0).astype(int)
nps = np.clip(np.round(rng.normal(7.3 - 1.2*np.clip(unhappy,0,None) - 0.3*c.NetworkComplaints90d - 0.25*c.BillingComplaints90d + 0.3*netq, 1.7)),0,10)
c["NPS"] = np.where(rng.random(N) < 0.4, np.nan, nps)

# ---------------- risk before Q1-26 campaign ----------------
yes = lambda s: (np.asarray(s)=="Yes").astype(float)
cte = np.nan_to_num(days_to_end, nan=999)
z0 = (-3.05
  + 0.45*pre + 1.1*secondary - 0.35*(c.SIMSlotRole=="Only SIM")
  - 0.012*np.minimum(ten,60)
  + np.where(cte<=60, 1.3, np.where(cte<=120, 0.5, 0)) - 0.6*((lock>0)&(cte>120))
  + np.where(pre, 0.035*np.nan_to_num(dslr), 0) + 0.45*yes(c.RechargeDowntrade) + 0.03*np.nan_to_num(c.ZeroBalanceDays30d)
  - 0.012*np.clip(c.ARPUChangePct.fillna(0),-60,30) - 0.008*np.clip(c.DataUsageChangePct.fillna(0),-80,50)
  - 0.20*np.clip(c.ActiveDays3mAvg.fillna(30)-25,-25,5)*0.3
  + 0.45*c.NetworkComplaints90d + 0.35*c.BillingComplaints90d + 0.35*c.RechargeFailureComplaints90d
  + 0.35*c.Escalations90d + 0.25*c.RepeatComplaints90d
  - 0.25*(c.IndoorCoverageScore-3) + 0.012*c.TowerOutageHours90d
  + 0.7*((c.Is5GDevice=="Yes")&(c.Our5GCoverage=="No")&(c.CompetitorNew5GLaunch90d=="Yes"))
  + 0.006*np.clip(c.PriceGapPct.fillna(0),-50,200)*np.clip(1+price_sens,0,None)*0.6
  + 0.5*yes(c.BillShock) + 0.0006*np.nan_to_num(dues)
  - 0.45*yes(c.ConvergedBundle) - 0.15*(c.FamilyPlanMembers-1) - 0.2*yes(c.HomeFiber)
  - 0.02*np.clip(c.AppLogins3m,0,40)
  + 0.25*(c.AcquisitionChannel=="MNP port-in")
  + 0.45*np.clip(unhappy,0,None) + rng.normal(0,0.55,N)).values

# ---------------- offer history (3 campaigns) ----------------
offers = {
 "10% loyalty discount (3 mo)":  (lambda a: 0.30*a, 0.24),
 "Free 10GB data add-on":         (lambda a: 49+0*a, 0.20),
 "Lock-in renewal: 1 month free": (lambda a: 1.0*a, 0.14),
 "Free OTT pack (6 mo)":          (lambda a: 149+0*a, 0.16),
 "Priority care (6 mo)":          (lambda a: 30+0*a, 0.10),
 "5G handset EMI cashback":       (lambda a: 1500+0*a, 0.08),
 "Double validity on next recharge": (lambda a: 0.5*a, 0.08)}
names = list(offers)
arpu = c.ARPU3mRs.fillna(c.ARPUPrev3mRs).fillna(250).values
heavy = np.nan_to_num(c.Data3mAvgGB.values) > np.nanpercentile(c.Data3mAvgGB, 60)
many_care = (c.CareContacts90d.values >= 1)
consent = (c.MarketingConsent=="Yes").values
def relevance(k, m):
    if k.startswith("10%"): return 0.4 + 0.6*(np.clip(price_sens[m],0,None)>0.5)
    if "data" in k: return 0.2 + 0.8*heavy[m]
    if "Lock-in" in k: return 0.1 + 0.8*(post[m] & (cte[m]<=120))
    if "OTT" in k: return 0.3 + 0.5*(age[m]<35)
    if "Priority" in k: return 0.2 + 0.7*many_care[m]
    if "5G" in k: return 0.1 + 0.6*((c.Is5GDevice.values[m]=="No") & (tier[m]!="Budget"))
    return 0.2 + 0.7*pre[m]
def effect(k, m):
    if k.startswith("10%"): return -0.6 - 0.8*(np.clip(price_sens[m],0,None)>0.5)
    if "data" in k: return -0.2 - 1.1*heavy[m]
    if "Lock-in" in k: return -0.4 - 1.4*(post[m] & (cte[m]<=120))
    if "OTT" in k: return -0.15 - 0.9*(age[m]<35)
    if "Priority" in k: return -0.2 - 1.1*many_care[m]
    if "5G" in k: return -0.05 + 0*age[m]
    return -0.3 - 0.8*pre[m]
camp_rows = []; eff = np.zeros(N); q1_group = np.full(N, "Not targeted", dtype=object)
q1 = {}
for cname, start, end, reach, is_main in [("Q3-FY26 Retention", "2025-07-07","2025-08-29", 0.10, False),
                                          ("Q4-FY26 Retention", "2025-10-06","2025-11-28", 0.12, False),
                                          ("Q1-CY26 Retention", "2026-01-05","2026-03-06", None, True)]:
    crm = sig(z0 + rng.normal(0,0.9,N))
    tgt = consent & (rng.random(N) < (np.clip(0.06+0.70*crm,0,0.9) if is_main else reach*(0.5+crm)))
    tgt &= (np.arange(N)>=0)
    hold = tgt & (rng.random(N) < (0.25 if is_main else 0.10))
    sent = tgt & ~hold
    offer = np.full(N, "", dtype=object); offer[sent] = rng.choice(names, sent.sum(), p=np.array([offers[k][1] for k in names])/sum(offers[k][1] for k in names))
    rel = np.zeros(N)
    for k in names:
        m = offer==k
        if m.any(): rel[m] = relevance(k, m)
    chan = np.where(sent, rng.choice(["SMS","App push","Outbound call","WhatsApp","Email"],N,p=[0.34,0.22,0.16,0.20,0.08]), "")
    cb = pd.Series(chan).map({"SMS":0,"App push":0.3,"Outbound call":0.6,"WhatsApp":0.4,"Email":-0.3,"":0}).values
    fatigue = np.zeros(N) if not camp_rows else pd.concat(camp_rows).query("Status!='Holdout'").groupby("CustomerID").size().reindex(c.CustomerID).fillna(0).values
    click = sent & (rng.random(N) < sig(-0.7 + 2.1*rel + cb - 0.35*fatigue + rng.normal(0,0.5,N)))
    acc = click & (rng.random(N) < sig(-0.3 + 1.8*rel + 0.3*cb + rng.normal(0,0.5,N)))
    sd = pd.Timestamp(start) + pd.to_timedelta(rng.integers(0,(pd.Timestamp(end)-pd.Timestamp(start)).days+1,N), unit="D")
    red = sd + pd.to_timedelta(rng.integers(0,10,N), unit="D")
    cost = np.zeros(N)
    for k in names:
        m = acc & (offer==k); cost[m] = offers[k][0](arpu[m])
    if is_main:
        for k in names:
            m = acc & (offer==k)
            if m.any(): eff[m] = effect(k, m) - (0.0 if "5G" in k else 0.35) + rng.normal(0,0.25,m.sum())
        q1_group = np.where(sent,"Offer sent",np.where(hold,"Holdout (no offer)","Not targeted"))
        q1 = dict(offer=offer, chan=chan, sd=sd, click=click, acc=acc, red=red, cost=cost, tgt=tgt, sent=sent)
    m = tgt
    camp_rows.append(pd.DataFrame({"CustomerID":c.CustomerID.values[m], "Campaign":cname,
        "Status": np.where(sent[m],"Offer sent","Holdout"), "Offer": offer[m], "Channel": chan[m],
        "SentDate": np.where(sent[m], sd[m].strftime("%Y-%m-%d"), sd[m].strftime("%Y-%m-%d")),
        "ExpiryDate": np.where(sent[m], (sd[m]+pd.Timedelta(days=21)).strftime("%Y-%m-%d"), ""),
        "Clicked": np.where(sent[m], np.where(click[m],"Yes","No"), ""),
        "Accepted": np.where(sent[m], np.where(acc[m],"Yes","No"), ""),
        "RedemptionDate": np.where(acc[m], red[m].strftime("%Y-%m-%d"), ""),
        "OfferCostRs": np.where(sent[m], np.round(cost[m]), np.nan)}))
oh = pd.concat(camp_rows, ignore_index=True)
oh.insert(0, "OfferRecordID", [f"O{i:06d}" for i in range(len(oh))])

# ---------------- churn outcome ----------------
z = z0 + eff
churn = rng.random(N) < sig(z)
c["OffersReceived12m"] = oh[oh.Status=="Offer sent"].groupby("CustomerID").size().reindex(c.CustomerID).fillna(0).astype(int).values
c["Q1CampaignGroup"] = q1_group
c["Q1Offer"] = q1["offer"]; c["Q1OfferChannel"] = q1["chan"]
c["Q1OfferDate"] = np.where(q1["tgt"], q1["sd"].strftime("%Y-%m-%d"), "")
c["Q1OfferClicked"] = np.where(q1["sent"], np.where(q1["click"],"Yes","No"), "")
c["Q1OfferAccepted"] = np.where(q1["sent"], np.where(q1["acc"],"Yes","No"), "")
c["Q1RedemptionDate"] = np.where(q1["acc"], q1["red"].strftime("%Y-%m-%d"), "")
c["Q1OfferCostRs"] = np.where(q1["sent"], np.round(q1["cost"]), np.nan)
c["EstimatedCLVRs"] = np.round(np.clip((arpu - c.CostToServeMonthlyRs.values)*12/np.clip(sig(z0)*4,0.08,None), 0, None), -1)
c["Churn"] = np.where(churn, "Yes","No")
c["ChurnDefinition"] = np.where(pre, "Prepaid: no recharge for 90 days after pack expiry, or port-out", "Postpaid: disconnection or port-out")

# ---- post-churn columns (known only after churn: NOT model features) ----
days = rng.integers(1, 91, N)
c["ChurnDate"] = np.where(churn, (SNAP + pd.to_timedelta(days, unit="D")).strftime("%Y-%m-%d"), "")
invol = churn & post & (np.nan_to_num(dues) > 400) & (rng.random(N)<0.85)
silent = churn & pre & ~invol & (rng.random(N) < sig(-1.4 + 0.035*np.nan_to_num(dslr) + 0.9*secondary))
port = churn & ~invol & ~silent & (rng.random(N) < 0.75)
c["ChurnType"] = np.select([invol, silent, port, churn], ["Involuntary (non-payment)","Silent (stopped recharging)","Voluntary (port-out)","Voluntary (disconnection)"], "")
# reason sampled from each customer's strongest drivers
drv = np.stack([
  0.6 + 0.02*np.clip(c.PriceGapPct.fillna(0),0,200) + 0.8*yes(c.BillShock) + 0.5*np.clip(price_sens,0,None),    # Price
  0.4 + 0.5*c.NetworkComplaints90d - 0.4*(c.IndoorCoverageScore-3) + 0.02*c.TowerOutageHours90d,                  # Network
  0.3 + 1.5*((c.Is5GDevice=="Yes")&(c.Our5GCoverage=="No")&(c.CompetitorNew5GLaunch90d=="Yes")) + 0.4*yes(c.CompetitorNew5GLaunch90d),  # Competitor offer / 5G
  0.3 + 0.5*c.BillingComplaints90d + 0.6*c.Escalations90d + 0.4*c.RepeatComplaints90d,                           # Service & care
  0.25 + 0*age,                                                                                                  # Relocation
  0.2 + 1.2*secondary], axis=1)                                                                                  # Using other SIM
drv = np.clip(drv, 0.05, None); drv = drv/drv.sum(1, keepdims=True)
rs = np.array(["Price / value","Network quality","Competitor offer / 5G","Service & care","Relocation","Using another SIM"])
reason = np.array([rs[rng.choice(6, p=p)] for p in drv])
reason = np.where(invol, "Non-payment", reason)
c["ChurnReason"] = np.where(churn, reason, "")
c["PortOutTo"] = np.where(port, rng.choice(["Competitor A","Competitor B","Competitor C"], N, p=[0.52,0.33,0.15]), "")
c["PortOutRequestDate"] = np.where(port, (pd.to_datetime(pd.Series(c.ChurnDate).replace("",None)) - pd.to_timedelta(rng.integers(3,8,N), unit="D")).dt.strftime("%Y-%m-%d").fillna(""), "")
win = churn & (rng.random(N) < 0.08)
c["ReactivatedWithin60d"] = np.where(churn, np.where(win,"Yes","No"), "")
c["SnapshotDate"] = SNAP.strftime("%Y-%m-%d")

# ---------------- light real-world messiness ----------------
def mess(col, frac, fn):
    i = rng.choice(N, int(frac*N), replace=False); c.loc[i, col] = c.loc[i, col].map(fn)
mess("Circle", 0.004, lambda s: s.upper()); mess("HandsetTier", 0.003, lambda s: " "+s+" ")
c.loc[rng.choice(N, 40, replace=False), "AvgDownloadMbps"] = np.nan
c.loc[rng.choice(N, 6, replace=False), "Voice3mAvgMin"] *= -1
c = pd.concat([c, c.sample(12, random_state=int(rng.integers(1e9)))]).sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)

order = ["CustomerID","SnapshotDate","Circle","Zone","Pincode","UrbanRural","Gender","Age","PlanType","AcquisitionChannel",
 "ActivationDate","TenureMonths","LockInMonths","ContractEndDate","DaysToContractEnd","FamilyPlanMembers","HomeFiber","DTH","ConvergedBundle",
 "HandsetTier","DeviceAgeMonths","Is5GDevice","DualSIM","SIMSlotRole","Our5GCoverage","AvgDownloadMbps","IndoorCoverageScore","TowerOutageHours90d",
 "ARPU3mRs","ARPUPrev3mRs","ARPUChangePct","Data3mAvgGB","DataPrev3mAvgGB","DataUsageChangePct","Voice3mAvgMin","ActiveDays3mAvg",
 "DroppedCallRate3mPct","AppLogins3m","DaysSinceLastRecharge","LastRechargeRs","PackValidityDays","Recharges90d","AvgRechargeRs3m",
 "AvgRechargeRsPrev3m","RechargeDowntrade","ZeroBalanceDays30d","ActiveDiscountPct","OverageCharges3mRs","BillShock","OutstandingDuesRs",
 "CostToServeMonthlyRs","EstimatedCLVRs","CompetitorCheapestPlanRs","PriceGapPct","CompetitorNew5GLaunch90d",
 "CareContacts90d","BillingComplaints90d","NetworkComplaints90d","RechargeFailureComplaints90d","RepeatComplaints90d","Escalations90d",
 "FirstContactResolutionRate","AvgResolutionDays90d","AvgCareSentiment90d","PreferredCareChannel","NPS",
 "MarketingConsent","OffersReceived12m","Q1CampaignGroup","Q1Offer","Q1OfferChannel","Q1OfferDate","Q1OfferClicked","Q1OfferAccepted",
 "Q1RedemptionDate","Q1OfferCostRs","Churn","ChurnDefinition","ChurnDate","ChurnType","ChurnReason","PortOutTo","PortOutRequestDate","ReactivatedWithin60d"]
assert set(order)==set(c.columns), set(c.columns)^set(order)
c[order].to_csv(f"{OUT}/customers.csv", index=False)
mu.to_csv(f"{OUT}/monthly_usage.csv", index=False)
care.to_csv(f"{OUT}/care_interactions.csv", index=False)
oh.to_csv(f"{OUT}/offer_history.csv", index=False)
print("seed", SEED, "| customers", len(c), "| monthly rows", len(mu), "| care rows", len(care), "| offer rows", len(oh))
=====END FILE: scripts/generate_india_sample.py=====

