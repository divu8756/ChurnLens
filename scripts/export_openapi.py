"""Write the FastAPI OpenAPI schema to frontend/openapi.json.

Run by `npm run gen:types` in frontend/, which then generates
frontend/lib/api-types.ts from it. No server or real key needed.
"""

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "openapi.json"

# The schema does not depend on these; placeholders let it run without backend/.env.
for name, value in {"GEMINI_API_KEY": "unused", "GEMINI_MODEL": "unused",
                    "GEMINI_MODEL_FAST": "unused"}.items():
    os.environ.setdefault(name, value)

sys.path.insert(0, str(ROOT / "backend"))
from app.main import create_app  # noqa: E402


def render() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
