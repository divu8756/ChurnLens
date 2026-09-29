"""Dot-path keys into graph state, e.g. "eda_results.categorical.Contract.levels.0.churn_rate".

Dict keys may themselves contain dots (column names such as "Rev.Q1"), so at
each dict level the longest matching key wins. List positions are integers.
"""

from typing import Any


class PathNotFound(KeyError):
    """The dot path does not resolve in the given data."""


_MISSING = object()


def resolve(data: Any, path: str) -> Any:
    if path == "":
        return data
    if isinstance(data, dict):
        matches = [k for k in data
                   if isinstance(k, str) and (path == k or path.startswith(k + "."))]
        for key in sorted(matches, key=len, reverse=True):
            rest = path[len(key) + 1:] if len(path) > len(key) else ""
            try:
                return resolve(data[key], rest)
            except PathNotFound:
                continue
        raise PathNotFound(path)
    if isinstance(data, list):
        head, _, rest = path.partition(".")
        if head.isdigit() and int(head) < len(data):
            return resolve(data[int(head)], rest)
        raise PathNotFound(path)
    raise PathNotFound(path)


def join(*parts: Any) -> str:
    return ".".join(str(p) for p in parts)


def try_resolve(data: Any, path: str) -> Any:
    try:
        return resolve(data, path)
    except PathNotFound:
        return _MISSING


def exists(data: Any, path: str) -> bool:
    return try_resolve(data, path) is not _MISSING
