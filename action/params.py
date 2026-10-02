"""인자 검사(GUARD A4) -- 한 벌(CMD-A4, BD-108). 원본은 MS `ToolSpec.check_args`(ms/tools.py:49-65) +
`PropertySpec.validate`(ms/model.py:78-107), stage-2 `2cb7e61`.

params: 이름 -> {"type": number · integer · string · bool · enum (없으면 number), "min", "max", "values", "unit",
                 "required"(기본 참)}

MS 와 다른 점 하나(docs/PREDICATE.md): 모르는 타입을 **문제로 적는다**(guard `params.py` 와 같다). MS 는 모르는 타입을 그냥
통과시킨다. ActionSpec(`action-spec/1`)은 지을 때 타입을 거르므로, 명세를 지난 params 에서는 둘이 같다.
"""
from __future__ import annotations

TYPES = ("number", "integer", "string", "bool", "enum")
KEYS = ("type", "unit", "min", "max", "values", "required")


def coerce(name: str, ps: dict, v):
    """(값, 문제). MS PropertySpec.validate 와 같다 -- 정수 자리의 1.0 은 1 로 읽는다."""
    t = ps.get("type", "number")
    unit = ps.get("unit", "")
    if t == "number":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None, f"{name}: 수가 아니다 ({v!r})"
        v = float(v)
        if v != v:
            return None, f"{name}: NaN"
    elif t == "integer":
        if isinstance(v, bool) or not isinstance(v, int):
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            else:
                return None, f"{name}: 정수가 아니다 ({v!r})"
    elif t == "string":
        if not isinstance(v, str):
            return None, f"{name}: 문자열이 아니다 ({v!r})"
    elif t == "bool":
        if not isinstance(v, bool):
            return None, f"{name}: 참거짓이 아니다 ({v!r})"
    elif t == "enum":
        if v not in (ps.get("values") or []):
            return None, f"{name}: {v!r} 는 {ps.get('values')} 밖이다"
    else:
        return None, f"{name}: 모르는 타입 {t!r}"
    if t in ("number", "integer"):
        if ps.get("min") is not None and v < ps["min"]:
            return None, f"{name}: {v} < 최소 {ps['min']}{unit}"
        if ps.get("max") is not None and v > ps["max"]:
            return None, f"{name}: {v} > 최대 {ps['max']}{unit}"
    return v, None


def check_args(params: dict, args) -> "list[str]":
    """문제 목록. 비었으면 맞다."""
    if not isinstance(args, dict):
        return ["args 가 객체가 아니다"]
    out = [f"모르는 인자 {k}" for k in args if k not in params]
    for k, ps in params.items():
        if k not in args:
            if ps.get("required", True):
                out.append(f"인자 {k} 가 없다")
            continue
        _, problem = coerce(k, ps, args[k])
        if problem:
            out.append(problem)
    return out


def spec_errors(params) -> "list[str]":
    """params 명세 자체의 모양. ActionSpec 이 지을 때 부른다."""
    if not isinstance(params, dict):
        return ["params: 객체가 아니다"]
    e = []
    for k, ps in params.items():
        if not isinstance(k, str) or not k:
            e.append(f"params: 이름 {k!r}")
            continue
        if not isinstance(ps, dict):
            e.append(f"params.{k}: 객체가 아니다")
            continue
        bad = sorted(set(ps) - set(KEYS))
        if bad:
            e.append(f"params.{k}: 모르는 칸 {bad}")
        if ps.get("type", "number") not in TYPES:
            e.append(f"params.{k}.type: {ps.get('type')!r}")
        if ps.get("type") == "enum" and not isinstance(ps.get("values"), list):
            e.append(f"params.{k}.values: enum 에는 목록이 있어야 한다")
        for b in ("min", "max"):
            if ps.get(b) is not None and (isinstance(ps[b], bool) or not isinstance(ps[b], (int, float))):
                e.append(f"params.{k}.{b}: 수가 아니다")
        if "required" in ps and not isinstance(ps["required"], bool):
            e.append(f"params.{k}.required: 참거짓이 아니다")
    return e
