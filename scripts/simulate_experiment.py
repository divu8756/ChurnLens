"""Generate an experiment results CSV with a KNOWN true effect (runbook T5c.5).

Reads an assignment (a downloaded assignment CSV, or an experiment ID fetched from a
running API) and writes a results file you can upload to /experiments/{id}/results.

Scenarios (seed 42), see backend/app/experiments/simulate.py:
  real_effect      control 26% vs treatment 21% churn, 45% acceptance
  no_effect        26% in both arms
  broken_delivery  real effect, but delivered 60/40 although 50/50 was planned

Examples:
  backend/.venv/bin/python scripts/simulate_experiment.py --assignment a.csv --out r.csv
  backend/.venv/bin/python scripts/simulate_experiment.py --experiment 3 \
      --api http://localhost:8010 --scenario no_effect --out r.csv
"""

import argparse
import io
import pathlib
import sys
import urllib.request

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.experiments.simulate import SCENARIOS, simulate_results  # noqa: E402


def load_assignment(args: argparse.Namespace) -> pd.DataFrame:
    if args.assignment:
        return pd.read_csv(args.assignment, dtype=str, keep_default_na=False)
    url = f"{args.api.rstrip('/')}/experiments/{args.experiment}/assignment.csv"
    if not url.startswith(("http://", "https://")):
        raise SystemExit("--api must be an http(s) URL")
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 (checked above)
        return pd.read_csv(io.BytesIO(response.read()), dtype=str, keep_default_na=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--assignment", type=pathlib.Path, help="assignment CSV file")
    source.add_argument("--experiment", type=int, help="experiment ID to fetch from --api")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="real_effect")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=pathlib.Path, required=True, help="results CSV to write")
    args = parser.parse_args()

    results = simulate_results(load_assignment(args), args.scenario, seed=args.seed)
    results.to_csv(args.out, index=False)
    split = results["group"].value_counts().to_dict()
    print(f"wrote {args.out} ({len(results):,} rows, {split}, scenario {args.scenario})")


if __name__ == "__main__":
    main()
