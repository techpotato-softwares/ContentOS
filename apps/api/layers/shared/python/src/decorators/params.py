from __future__ import annotations
from enum import Enum

class ParamType(str, Enum):
    PARAM = "param"
    QUERY = "query"
    BODY = "body"
    USER = "user"
    EVENT = "event"

def _param(ptype: ParamType, name: str | None = None):
    def deco(fn=None):
        # Used as annotation helper; FastAPI-style markers stored on function
        def wrapper(func):
            params = getattr(func, "__param_meta__", [])
            params.append({"type": ptype, "name": name})
            func.__param_meta__ = params
            return func
        return wrapper if fn is None else wrapper(fn)
    return deco

def Param(name: str):
    return _param(ParamType.PARAM, name)

def Query(name: str | None = None):
    return _param(ParamType.QUERY, name)

def Body():
    return _param(ParamType.BODY)

def CurrentUser():
    return _param(ParamType.USER)

def Event():
    return _param(ParamType.EVENT)
