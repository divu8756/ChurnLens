"""Pre-commit secret check. Prints only PASS or FAIL with file names.

1. backend/.env must be git-ignored.
2. No tracked, staged or untracked-but-not-ignored file may contain the
   Gemini key value (read from backend/.env at runtime, never stored).
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "backend" / ".env"


def read_secret_values() -> list[str]:
    if not ENV_FILE.exists():
        return []
    values = []
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if len(value) >= 10:
                values.append(value)
    return values


def main() -> int:
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "backend/.env"], cwd=ROOT
    ).returncode == 0
    if not ignored:
        print("FAIL: backend/.env is not git-ignored")
        return 1

    secrets = read_secret_values()
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    hits = []
    for name in listed:
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(s in text for s in secrets):
            hits.append(name)

    if hits:
        print("FAIL: " + ", ".join(hits))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
