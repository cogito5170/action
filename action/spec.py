"""행동 명세 -- ActionSpec 하나, 집 하나(CMD-A3 E1 설계안의 증명. docs/EXECUTOR.md §1).

지금 셋으로 갈라진 것을 모은다: DC `purpose.ActionSpec`(이름 · 능력) · MS `ToolSpec`(인자 · 사전조건 · 위험) ·
guard `GuardModel` 의 ActionSpec(MS 의 다섯 칸 그대로) · Health 의 사후조건 · 창(아직 집이 없다).

    ActionSpec  name · version · target_model · params · preconditions · risk · postcondition · window_ms · description
    ActionModel version · specs   -- 판본 있는 묶음. 실행 중 읽기만 한다

투영(소비자마다 필요한 칸만):
    to_ms_tool(spec)      MS ToolSpec.from_dict 가 받는 dict (handler · effect 는 MS 런타임이 이름으로 붙인다)
    to_guard_spec(spec)   guard ActionSpec(name, target_model, params, preconditions, risk) 의 인자
    verify_args(spec)     health.verify 의 spec · postcondition · window_ms

**허가(grants) · 막는 위험 등급(risky) · 안전 동작 순서는 여기 없다.** 그것은 배치마다 다른 운영자 권한 · 가정이다(Guard · Model 설정).
술어는 모양만 본다(연산 이름 · 칸 수). 참 · 거짓 판정은 MS · guard · health 의 술어 모듈이 한다 -- 그것을 한 벌로 모으는 일은 E2.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .canonical import check_json, digest
from .forms import ContractError

SPEC_SCHEMA = "action-spec/1"
MODEL_SCHEMA = "action-model/1"
RISKS = ("read", "local", "external", "irreversible")         # MS tools.py · guard views.py 와 같다
BINARY_OPS = ("==", "!=", "<", "<=", ">", ">=", "in", "not_in")  # MS predicate.OPS 와 같다(시험이 대조)
UNARY_OPS = ("exists", "missing")
PARAM_KEYS = ("type", "min", "max", "values", "unit", "required")
PARAM_TYPES = ("integer", "number", "string", "boolean", "enum")
ENTITY_REF = re.compile(r"^(\$target|\$run\.(agent|task|runtime)|[^$\s][^\s]*)$")   # health verification.py:74-79 와 같다
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _pred_errors(p, where: str, refs: bool) -> "list[str]":
    if not isinstance(p, (list, tuple)) or len(p) not in (2, 3):
        return [f"{where}: [속성, 연산, 값] 이 아니다 ({p!r})"]
    if not isinstance(p[0], str) or not p[0]:
        return [f"{where}: 속성 이름이 문자열이 아니다 ({p[0]!r})"]
    if len(p) == 2:
        return [] if p[1] in UNARY_OPS else [f"{where}: 값 없는 연산은 {UNARY_OPS} 뿐 ({p[1]!r})"]
    if p[1] not in BINARY_OPS:
        return [f"{where}: 모르는 연산 {p[1]!r}"]
    v = p[2]
    if isinstance(v, dict):
        if not refs:
            return [f"{where}: 속성 참조는 쓸 수 없다(사후조건, V4)"]
        return [] if set(v) <= {"prop", "mul"} and isinstance(v.get("prop"), str) else [f"{where}: 속성 참조 꼴 {v!r}"]
    return [f"{where}: {e}" for e in check_json(v, "값")]


def _plain(p):
    return [list(x) if isinstance(x, tuple) else x for x in p]


@dataclass(frozen=True)
class ActionSpec:
    name: str
    version: str
    target_model: "str | None" = "*"   # "*" 아무 모형 · None 겨냥 없는 행동(STOP · ESCALATE)
    params: dict = field(default_factory=dict)
    preconditions: tuple = ()          # 대상의 **지금** 상태 [속성, 연산, 값] -- GUARD A6
    risk: str = "local"
    postcondition: tuple = ()          # {"entity": "$target" | "$run.<역할>" | 실체 id, "pred": [상태, 연산, 값]} 의 논리곱 -- VERIFY
    window_ms: "float | None" = None   # 사후조건을 기다리는 길이. 사후조건이 있으면 있어야 한다
    description: str = ""
    schema: str = SPEC_SCHEMA

    def __post_init__(self):
        object.__setattr__(self, "preconditions", tuple(tuple(p) if isinstance(p, list) else p for p in self.preconditions)
                           if isinstance(self.preconditions, (list, tuple)) else self.preconditions)
        object.__setattr__(self, "postcondition", tuple(self.postcondition)
                           if isinstance(self.postcondition, list) else self.postcondition)
        e = []
        if self.schema != SPEC_SCHEMA:
            e.append(f"schema: {self.schema!r}")
        if not isinstance(self.name, str) or not NAME.match(self.name):
            e.append(f"name: {self.name!r}")
        if not isinstance(self.version, str) or not self.version or "@" in self.version or " " in self.version:
            e.append(f"version: {self.version!r}")
        if self.target_model is not None and (not isinstance(self.target_model, str) or not self.target_model):
            e.append(f"target_model: {self.target_model!r}")
        if not isinstance(self.params, dict):
            e.append("params: 객체가 아니다")
        else:
            for k, ps in self.params.items():
                if not isinstance(ps, dict) or set(ps) - set(PARAM_KEYS):
                    e.append(f"params.{k}: 모르는 칸 {sorted(set(ps) - set(PARAM_KEYS)) if isinstance(ps, dict) else ps!r}")
                elif ps.get("type") not in PARAM_TYPES:
                    e.append(f"params.{k}.type: {ps.get('type')!r}")
                else:
                    e += [f"params.{k}: {x}" for x in check_json(ps)]
        if not isinstance(self.preconditions, tuple):
            e.append("preconditions: 목록이 아니다")
        else:
            for i, p in enumerate(self.preconditions):
                e += _pred_errors(p, f"preconditions[{i}]", refs=True)
        if self.risk not in RISKS:
            e.append(f"risk: {self.risk!r}")
        if not isinstance(self.postcondition, tuple):
            e.append("postcondition: 목록이 아니다")
        else:
            for i, c in enumerate(self.postcondition):
                if not isinstance(c, dict) or set(c) != {"entity", "pred"}:
                    e.append(f"postcondition[{i}]: {{entity, pred}} 가 아니다")
                    continue
                if not isinstance(c["entity"], str) or not ENTITY_REF.match(c["entity"]):
                    e.append(f"postcondition[{i}].entity: {c['entity']!r}")
                if c["entity"] == "$target" and self.target_model is None:
                    e.append(f"postcondition[{i}]: 겨냥 없는 행동에 $target")
                e += _pred_errors(c["pred"], f"postcondition[{i}].pred", refs=False)
        if self.window_ms is not None and (isinstance(self.window_ms, bool) or not isinstance(self.window_ms, (int, float))
                                           or not math.isfinite(self.window_ms) or self.window_ms <= 0):
            e.append(f"window_ms: 0 보다 큰 수가 아니다 ({self.window_ms!r})")
        if isinstance(self.postcondition, tuple) and self.postcondition and self.window_ms is None:
            e.append("window_ms: 사후조건이 있으면 창이 있어야 한다")
        if not isinstance(self.description, str):
            e.append("description: 문자열이 아니다")
        if e:
            raise ContractError("ActionSpec", e)

    @property
    def ref(self) -> str:
        """Health 의 `spec` 칸("이름@판본")."""
        return f"{self.name}@{self.version}"

    def to_dict(self) -> dict:
        return {"schema": self.schema, "name": self.name, "version": self.version, "target_model": self.target_model,
                "params": self.params, "preconditions": _plain(self.preconditions), "risk": self.risk,
                "postcondition": [dict(c, pred=list(c["pred"])) for c in self.postcondition],
                "window_ms": self.window_ms, "description": self.description}

    def digest(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "ActionSpec":
        if not isinstance(d, dict):
            raise ContractError("ActionSpec", ["객체가 아니다"])
        known = set(cls.__dataclass_fields__)
        bad = sorted(set(d) - known)
        if bad:
            raise ContractError("ActionSpec", [f"모르는 칸 {bad}"])
        missing = sorted({"name", "version", "schema"} - set(d))
        if missing:
            raise ContractError("ActionSpec", [f"빠진 칸 {missing}"])
        return cls(**d)

    @classmethod
    def from_tool(cls, tool: dict, version: str, postcondition=(), window_ms=None) -> "ActionSpec":
        """MS 의 도구 정의(JSON) → ActionSpec. handler · effect 는 실행 쪽 결합이라 버린다(MS 가 이름으로 다시 붙인다)."""
        keep = {k: tool[k] for k in ("name", "target_model", "params", "preconditions", "risk", "description") if k in tool}
        return cls(version=version, postcondition=tuple(postcondition), window_ms=window_ms, **keep)


@dataclass(frozen=True)
class ActionModel:
    version: str
    specs: tuple                       # ActionSpec 들. 이름이 겹치면 거절
    schema: str = MODEL_SCHEMA

    def __post_init__(self):
        e = []
        if self.schema != MODEL_SCHEMA:
            e.append(f"schema: {self.schema!r}")
        if not isinstance(self.version, str) or not self.version:
            e.append(f"version: {self.version!r}")
        specs = tuple(s if isinstance(s, ActionSpec) else ActionSpec.from_dict(s) for s in self.specs)
        names = [s.name for s in specs]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            e.append(f"겹치는 이름 {dup}")
        if e:
            raise ContractError("ActionModel", e)
        object.__setattr__(self, "specs", tuple(sorted(specs, key=lambda s: s.name)))

    def get(self, name: str) -> "ActionSpec | None":
        return next((s for s in self.specs if s.name == name), None)

    def names(self) -> "tuple[str, ...]":
        return tuple(s.name for s in self.specs)

    def to_dict(self) -> dict:
        return {"schema": self.schema, "version": self.version, "specs": [s.to_dict() for s in self.specs]}

    def digest(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "ActionModel":
        if not isinstance(d, dict) or set(d) - {"schema", "version", "specs"} or "version" not in d:
            raise ContractError("ActionModel", [f"꼴이 아니다 ({sorted(d) if isinstance(d, dict) else d!r})"])
        return cls(d["version"], tuple(d.get("specs", ())), d.get("schema", MODEL_SCHEMA))


# ── 투영 ───────────────────────────────────────────────────────────────────

def to_ms_tool(spec: ActionSpec) -> dict:
    return {"name": spec.name, "target_model": spec.target_model, "description": spec.description,
            "params": spec.params, "preconditions": _plain(spec.preconditions), "risk": spec.risk}


def to_guard_spec(spec: ActionSpec) -> dict:
    return {"name": spec.name, "target_model": spec.target_model, "params": spec.params,
            "preconditions": tuple(spec.preconditions), "risk": spec.risk}


def verify_args(spec: ActionSpec) -> dict:
    return {"spec": spec.ref, "postcondition": [dict(c, pred=list(c["pred"])) for c in spec.postcondition],
            "window_ms": spec.window_ms}
