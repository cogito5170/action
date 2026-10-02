"""술어 `[속성, 연산, 값]` -- 한 벌(CMD-A4, BD-108). 원본은 MS `ms/predicate.py`(stage-2 `2cb7e61`)다.

모형의 파생 상태 · 질의 거르개 · 행동의 사전조건(GUARD A6) · 사후조건(VERIFY)이 같은 언어를 쓴다. `eval` 은 없다. 연산은 아래 표가 전부다.

- 값 자리에 다른 속성을 걸 수 있다: `{"prop": 이름, "mul": 수}`. 걸린 속성이 없거나 수가 아니면 거짓.
- 속성이 없으면 거짓(`exists` · `missing` 은 그것을 묻는 연산). 비교할 수 없는 값도 거짓 -- 모르는 것을 참으로 세지 않는다.

MS · guard · health 의 벌과 다른 점(docs/PREDICATE.md):
- `check(pred, refs=True, named=False)`: 기본은 MS 와 같다. health(verification-record/1)는 `refs=False, named=True` 로 부른다
  -- 속성 참조를 받지 않고, 첫 칸이 빈 것 아닌 문자열이어야 한다.
- `props_of` 는 **처음 나온 순서의 목록**이다(guard 와 같다). MS 는 집합을 돌려준다 -- MS 는 `set(props_of(...))` 로 쓴다.
"""
from __future__ import annotations

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}
UNARY = ("exists", "missing")
REF_OPS = ("<", "<=", ">", ">=", "==", "!=")


def check(pred, refs: bool = True, named: bool = False) -> "list[str]":
    """모양이 틀린 술어를 미리 잡는다. 문제 목록(비었으면 성하다).
    refs=False: 값 자리의 속성 참조를 받지 않는다. named=True: 첫 칸이 빈 것 아닌 문자열이어야 한다."""
    if not isinstance(pred, (list, tuple)) or len(pred) not in (2, 3):
        return [f"술어는 [속성, 연산, 값] 이어야 한다: {pred!r}"]
    if named and (not isinstance(pred[0], str) or not pred[0]):
        return [f"술어의 첫 칸은 빈 것 아닌 문자열이어야 한다: {pred!r}"]
    if len(pred) == 2:
        return [] if pred[1] in UNARY else [f"값 없는 연산은 exists · missing 뿐: {pred!r}"]
    if pred[1] not in OPS:
        return [f"모르는 연산 {pred[1]!r} (쓸 수 있는 것: {', '.join(OPS)} · exists · missing)"]
    if pred[1] in ("in", "not_in") and not isinstance(pred[2], (list, tuple)):
        return [f"{pred[1]} 의 값은 목록이어야 한다: {pred!r}"]
    if isinstance(pred[2], dict):
        if not refs:
            return [f"속성 참조를 받지 않는 자리다: {pred!r}"]
        if set(pred[2]) - {"prop", "mul"} or not isinstance(pred[2].get("prop"), str):
            return [f"속성 참조는 {{\"prop\": 이름, \"mul\": 수}} 꼴이어야 한다: {pred!r}"]
        if pred[1] not in REF_OPS:
            return [f"속성 참조는 비교 연산에만: {pred!r}"]
    return []


def _rhs(v, values):
    if isinstance(v, dict) and "prop" in v:
        ref = values.get(v["prop"])
        if ref is None or isinstance(ref, bool) or not isinstance(ref, (int, float)):
            return None
        return ref * v.get("mul", 1)
    return v


def holds(pred, values: dict) -> bool:
    prop, op = pred[0], pred[1]
    if op == "exists":
        return values.get(prop) is not None
    if op == "missing":
        return values.get(prop) is None
    if values.get(prop) is None:
        return False
    rhs = _rhs(pred[2], values)
    if rhs is None:
        return False
    try:
        return bool(OPS[op](values[prop], rhs))
    except TypeError:
        return False


def all_hold(preds, values: dict) -> bool:
    return all(holds(p, values) for p in preds)


def props_of(preds) -> list:
    """술어들이 읽는 속성(걸린 속성 포함). 처음 나온 순서, 겹침 없이."""
    out = []
    for p in preds:
        for name in [p[0]] + ([p[2]["prop"]] if len(p) > 2 and isinstance(p[2], dict) and "prop" in p[2] else []):
            if name not in out:
                out.append(name)
    return out
