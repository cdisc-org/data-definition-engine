"""A disk-caching wrapper around ``CDISCLibraryClient``.

The Define loader re-fetches the same codelists once per variable, and the CRF loader adds
CDASH CT on top — roughly doubling CT volume. This wrapper caches every response as JSON
on disk, keyed by a hash of the call, so repeat runs during a refinement loop cost nothing.

It proxies by delegation rather than subclassing, so any client method is usable whether
or not it is cached; only the read-only ``get_*`` methods are intercepted.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = ".cache/cdisc_library"

#: Client methods whose results are cached. All are read-only lookups.
CACHED_METHODS = frozenset({
    "get_api_json",
    "get_codelist_terms",
    "get_codelist_term",
    "get_cdash",
    "get_cdashig",
    "get_qrs_instrument",
    "get_biomedicalconcept_latest_datasetspecializations",
    "get_sdtm_latest_sdtm_datasetspecialization",
})


class CachingLibraryClient:
    """Delegating proxy that caches CDISC Library GET responses on disk."""

    def __init__(self, client: Any, cache_dir: str | Path = DEFAULT_CACHE_DIR,
                 enabled: bool = True) -> None:
        """
        :param client: the wrapped ``CDISCLibraryClient``
        :param cache_dir: directory for cached JSON payloads
        :param enabled: when False every call passes straight through
        """
        self._client = client
        self._cache_dir = Path(cache_dir)
        self._enabled = enabled
        self.hits = 0
        self.misses = 0
        if self._enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if not self._enabled or name not in CACHED_METHODS or not callable(attr):
            return attr
        return self._wrap(name, attr)

    def _wrap(self, name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        def cached(*args: Any, **kwargs: Any) -> Any:
            path = self._cache_path(name, args, kwargs)
            if path.exists():
                self.hits += 1
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    # A truncated cache entry must never look like a Library miss.
                    logger.warning("discarding unreadable cache entry %s: %s", path, exc)
                    path.unlink(missing_ok=True)
            self.misses += 1
            result = func(*args, **kwargs)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(result, f)
            except (TypeError, OSError) as exc:
                logger.debug("could not cache %s: %s", name, exc)
            return result

        return cached

    def _cache_path(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Path:
        key = json.dumps([name, args, sorted(kwargs.items())], default=str, sort_keys=True)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self._cache_dir / f"{name}.{digest}.json"

    def summary(self) -> str:
        """One-line cache summary for the end-of-run report."""
        if not self._enabled:
            return "library cache: disabled"
        return f"library cache: {self.hits} hit(s), {self.misses} miss(es) in {self._cache_dir}"
