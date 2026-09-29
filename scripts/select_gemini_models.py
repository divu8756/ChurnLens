"""Pick the newest stable Gemini Pro and Flash models and write them to backend/.env.

The API key is read from backend/.env and sent only in the x-goog-api-key
header. It is never printed, logged or put in a URL.
Exit codes: 0 ok, 2 key rejected, 1 other failure.
"""

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "backend" / ".env"
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
# Stable names only, e.g. models/gemini-2.5-pro or models/gemini-2.5-flash-001.
STABLE = re.compile(r"^models/gemini-(\d+(?:\.\d+)?)-(pro|flash)(?:-\d{3})?$")


def read_env() -> list[str]:
    return ENV_FILE.read_text(encoding="utf-8").splitlines()


def get_key(lines: list[str]) -> str:
    for line in lines:
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def list_models(key: str) -> list[dict]:
    req = urllib.request.Request(MODELS_URL, headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("models", [])


def pick(models: list[dict], family: str) -> str | None:
    best: tuple[float, str] | None = None
    for m in models:
        name = m.get("name", "")
        match = STABLE.match(name)
        if not match or match.group(2) != family:
            continue
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        version = float(match.group(1))
        short = name.removeprefix("models/")
        # Prefer the higher version; for equal versions prefer the unsuffixed alias.
        if best is None or version > best[0] or (version == best[0] and len(short) < len(best[1])):
            best = (version, short)
    return best[1] if best else None


def write_env(lines: list[str], updates: dict[str, str]) -> None:
    out, seen = [], set()
    for line in lines:
        k = line.split("=", 1)[0]
        if k in updates:
            out.append(f"{k}={updates[k]}")
            seen.add(k)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def main() -> int:
    lines = read_env()
    key = get_key(lines)
    if not key:
        print("GEMINI_API_KEY is missing in backend/.env")
        return 2
    try:
        models = list_models(key)
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            print(f"Key rejected by the Gemini API (HTTP {e.code}).")
            return 2
        print(f"Gemini API error: HTTP {e.code}")
        return 1
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}")
        return 1

    pro, flash = pick(models, "pro"), pick(models, "flash")
    if not pro or not flash:
        print(f"Could not find stable models (pro={pro}, flash={flash})")
        return 1
    write_env(lines, {"GEMINI_MODEL": pro, "GEMINI_MODEL_FAST": flash})
    print(f"GEMINI_MODEL={pro}")
    print(f"GEMINI_MODEL_FAST={flash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
