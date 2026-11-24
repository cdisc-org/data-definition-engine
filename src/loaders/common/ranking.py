"""Rank dictionary-style entries for one object: shared by the defaults dictionary and the methods library.

An entry names the objects it applies to by ``name``: the object's name exactly, a suffix (``--SEQ``
matches any longer name ending in ``SEQ``), or ``*`` (every object, which a caller pairs with
``domains``). ``domains`` and ``excludeDomains`` narrow it to datasets. Candidates for an object are
ranked best first:

1. an exact name, then a longer suffix before a shorter one, then ``*``;
2. at equal rank, whatever the caller adds through ``extra`` (the methods library puts a matching
   ``where`` here, so a value-level entry outranks one without);
3. then an entry with domain filters before one without;
4. then a later file before an earlier one, and a later entry before an earlier one.
"""
from __future__ import annotations

from typing import AbstractSet


def name_kind(pattern: str, name: str | None) -> tuple[int, int] | None:
    """How ``pattern`` matches ``name``: exact ``(3, 0)``, suffix ``(2, len(suffix))``, ``*`` ``(1, 0)``;
    None when it does not."""
    if pattern == "*":
        return 1, 0
    if pattern.startswith("--"):
        suffix = pattern[2:]
        if not name or not name.endswith(suffix) or len(name) <= len(suffix):
            return None
        return 2, len(suffix)
    if pattern == name:
        return 3, 0
    return None


def domain_admits(domains: AbstractSet[str] | None, exclude: AbstractSet[str] | None,
                  domain: str | None) -> bool:
    """Whether the dataset filters let an entry apply in ``domain``."""
    if domains is not None and domain not in domains:
        return False
    return exclude is None or domain not in exclude


def rank(pattern: str, name: str | None, domain: str | None, *,
         domains: AbstractSet[str] | None = None, exclude: AbstractSet[str] | None = None,
         order: int = 0, position: int = 0, extra: tuple = ()) -> tuple | None:
    """An entry's rank for an object (higher is better), or None when it does not apply."""
    if not domain_admits(domains, exclude, domain):
        return None
    kind = name_kind(pattern, name)
    if kind is None:
        return None
    filtered = 1 if (domains is not None or exclude is not None) else 0
    return kind + tuple(extra) + (filtered, order, position)
