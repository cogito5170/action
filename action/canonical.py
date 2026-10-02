"""정준 JSON -- 내용 해시용 한 가지 바이트열.

MS `ms/decision_record.py` 의 방식(`json.dumps(sort_keys=True, ensure_ascii=False)` → sha256 앞 16 hex)을 따른다.
다른 점 둘: 구분자를 `(",", ":")` 로 고정하고, `default=str` 을 쓰지 않는다 -- JSON 이 아닌 값이 해시에 몰래 문자열로
들어가지 않게 거절한다. NaN · 무한대도 거절한다(JSON 이 아니고, 해시가 플랫폼마다 같다는 보장이 없다).
"""
from __future__ import annotations

import hashlib
import json

_SCALAR = (str, int, float, bool, type(None))


def check_json(v, path: str = "$") -> "list[str]":
    """JSON 값(기본 타입 · 문자열 열쇠 객체 · 목록)인가. 빈 목록이면 통과."""
    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
        return [f"{path}: 유한하지 않은 수 {v!r}"]
    if isinstance(v, _SCALAR):
        return []
    if isinstance(v, list):
        return [e for i, x in enumerate(v) for e in check_json(x, f"{path}[{i}]")]
    if isinstance(v, dict):
        errs = [f"{path}: 문자열이 아닌 열쇠 {k!r}" for k in v if not isinstance(k, str)]
        return errs + [e for k, x in v.items() if isinstance(k, str) for e in check_json(x, f"{path}.{k}")]
    return [f"{path}: JSON 이 아닌 값 {type(v).__name__}"]


def canonical_json(obj) -> str:
    errs = check_json(obj)
    if errs:
        raise ValueError(f"정준 JSON 이 될 수 없다: {errs}")
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(obj) -> str:
    """정준 JSON 의 sha256 앞 16 hex."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()[:16]
