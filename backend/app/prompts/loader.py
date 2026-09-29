"""Load versioned prompt files (backend/app/prompts/<name>.v<N>.md) and fill {{variables}}."""

import re
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_VERSION = re.compile(r"^<!--\s*version:\s*(\S+)\s*-->", re.M)


class PromptError(ValueError):
    """Missing prompt file, missing version header, or missing/extra variables."""


@lru_cache
def read_prompt(name: str, version: int) -> str:
    path = PROMPTS_DIR / f"{name}.v{version}.md"
    if not path.exists():
        raise PromptError(f"Prompt file not found: {path.name}")
    text = path.read_text(encoding="utf-8")
    match = _VERSION.search(text)
    if not match or match.group(1) != f"{name}.v{version}":
        raise PromptError(f"{path.name} must start with <!-- version: {name}.v{version} -->")
    return text


def prompt_variables(name: str, version: int) -> set[str]:
    return set(_VAR.findall(read_prompt(name, version)))


def render_prompt(name: str, version: int, **values: str) -> str:
    template = read_prompt(name, version)
    needed = set(_VAR.findall(template))
    missing = needed - values.keys()
    if missing:
        raise PromptError(f"{name}.v{version} is missing variables: {sorted(missing)}")
    extra = values.keys() - needed
    if extra:
        raise PromptError(f"{name}.v{version} got unknown variables: {sorted(extra)}")
    return _VAR.sub(lambda m: values[m.group(1)], template)
