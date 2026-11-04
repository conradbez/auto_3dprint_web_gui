"""Project RAGs for map/ templates.

rag_file(path)       -> the text of a repo file (e.g. README.md), so prompts read the
                        real decisions instead of a pasted copy that drifts.
rag_brave_search(q)  -> extras' Brave search, disk-cached and paced for the Free plan.
"""
import hashlib
import json
import time
from pathlib import Path


import promptmap
from promptmap import rag as _rag

ROOT = Path(__file__).parent
CACHE = ROOT / ".rag_cache"

# Brave Free plan = 1 request/s; brave_findings fires 4 queries back to back and
# got 429 RATE_LIMITED. Wrap the extras' rag_brave_search under the same name:
# disk-cached by (query, count) and paced to 1 call per 1.1 s.
_rag.load_plugins()  # so ours registers last and wins
_brave = _rag.get_rag_kind("brave_search")
_last_brave = [0.0]


def _cached(prefix: str, key: str):
    CACHE.mkdir(exist_ok=True)
    return CACHE / (prefix + hashlib.sha256(key.encode()).hexdigest()[:16] + ".json")


@promptmap.rag_kind("brave_search")
def rag_brave_cached(query: str, count: int = 8) -> list[str]:
    key = _cached("brave_", f"{query}|{count}")
    if key.exists():
        return json.loads(key.read_text())["hits"]
    wait = 1.1 - (time.monotonic() - _last_brave[0])
    if wait > 0:
        time.sleep(wait)
    hits = _brave(query, count=count)
    _last_brave[0] = time.monotonic()
    key.write_text(json.dumps({"query": query, "hits": hits}))
    return hits


@promptmap.rag_kind("file")
def rag_file(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")
