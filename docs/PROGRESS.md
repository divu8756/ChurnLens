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
