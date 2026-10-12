"""Shared helpers for the Geely EM integration."""
from __future__ import annotations

from typing import Any


def dig(d: Any, path: str) -> Any:
    """Read a dotted path from nested dicts/lists, returning None when missing.

    Numeric path segments index into lists (e.g. ``settings.0.sts``).
    """
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur
