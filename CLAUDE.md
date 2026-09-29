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
