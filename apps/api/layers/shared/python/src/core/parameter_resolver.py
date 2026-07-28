from __future__ import annotations
import json
import inspect
from typing import Any

def resolve_parameters(fn, event: dict, path_params: dict[str, str]) -> list[Any]:
    """Resolve args by parameter names / annotations (simple convention)."""
    sig = inspect.signature(fn)
    args = []
    body = None
    raw = event.get("body")
    if raw:
        try:
            body = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            body = {}
    qs = event.get("queryStringParameters") or {}
    user = event.get("user")

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if name in path_params:
            args.append(path_params[name])
        elif name in ("data", "body", "payload"):
            args.append(body or {})
        elif name == "user" or name == "current_user":
            args.append(user)
        elif name == "event":
            args.append(event)
        elif name in ("query", "query_params", "qs"):
            args.append(qs)
        elif name in qs:
            args.append(qs[name])
        elif param.default is not inspect.Parameter.empty:
            args.append(param.default)
        else:
            args.append(None)
    return args
