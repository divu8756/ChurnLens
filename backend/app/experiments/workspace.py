"""Workspace scoping: each browser sends a random key (X-Workspace-Key); experiments,
their evidence and uploads are tied to its SHA-256 hash, so visitors of a shared
deployment never see (or are influenced by) each other's experiments. Only the hash
is stored. It is an unguessable bearer key, not a login."""

import hashlib
import re
from typing import Annotated

from fastapi import Header, HTTPException

HEADER = "X-Workspace-Key"
_KEY = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def optional_workspace(
    key: Annotated[str | None, Header(alias=HEADER)] = None,
) -> str | None:
    """Hash of a valid key, or None when the header is absent (uploads)."""
    if key is None:
        return None
    if not _KEY.match(key):
        raise HTTPException(400, f"{HEADER} must be 16-128 letters, digits, '-' or '_'.")
    return hash_key(key)


def required_workspace(
    key: Annotated[str | None, Header(alias=HEADER)] = None,
) -> str:
    hashed = optional_workspace(key)
    if hashed is None:
        raise HTTPException(400, f"Send an {HEADER} header to use experiments.")
    return hashed
