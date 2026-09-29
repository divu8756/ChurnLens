# ChurnLens progress

Project root: /Users/divyanshusrivastava/ChurnLens

## Current task
T1.1

## Next step
T1.1: restate the architecture, draw the LangGraph flow, list top risks.

## Done
- Bootstrap: plan, spec, rules, settings, data generators and backend/.env unpacked.
- Preflight: tools checked, Gemini models selected, gh logged in, secret check in place.
- Sample data generated: telco_churn.csv (7,014 rows = 7,000 unique + 14 duplicates,
  11 blank TotalCharges) and the 4-table India dataset (git-ignored, regenerate
  with scripts/generate_india_sample.py).

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
- Gemini models (scripts/select_gemini_models.py, newest stable, non-preview):
  GEMINI_MODEL=gemini-2.5-pro, GEMINI_MODEL_FAST=gemini-3.8-flash.
- Sample data is synthetic and IBM-Telco-style (fixed seed 20260331); India
  4-table demo dataset (fixed seed 20260401).

## Checkpoints for the human
- Preflight: the only stable Pro model is gemini-2.5-pro (Gemini 3.x Pro exists
  only as preview), while the stable Flash is gemini-3.8-flash, a newer
  generation. The rule says "newest stable Pro", so the older Pro is used for
  GEMINI_MODEL. If you prefer, set GEMINI_MODEL=gemini-3.8-flash in backend/.env.

## Known issues

## Human actions needed
- S7 at the end: Render + Vercel dashboard steps (paste GEMINI_API_KEY into Render yourself).
