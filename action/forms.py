"""행동 꼴 셋 -- ActionIntent(DECIDE) → ActionCommand(GUARD → EXECUTE) → ActionOutcome(EXECUTE). BD-25.

칸은 baseline `SCHEMA_PROPOSAL.md` §2.6 의 표를 따른다. 표와 다른 곳은 칸 옆 주석과 `docs/CONTRACT.md` §3 에 까닭이 있다.

규칙
- **닫힌 꼴.** `from_dict` 는 모르는 칸 · 빠진 칸 · 다른 판본(`schema`)을 거절한다. 객체를 지을 때도 칸마다 타입 · 값을 검사한다.
- **id 는 내용 해시다.** `intent_id` · `command_id` 는 나머지 칸 전부의 정준 JSON(`canonical.py`)에서 나온다(MS DecisionRecord 와
  같은 방식). 그래서 받는 쪽이 다시 계산해 고쳐졌는지 안다 -- `from_dict` 에서 맞지 않으면 거절한다.
- **ActionOutcome 은 원장이 아니다.** L0 `action.result` 사건의 칸과 1:1 이다(`l0map.py`). 새 원장을 만들지 않는다.
  못 본 값은 None 이고, 기본값으로 메우지 않는다(L0 규칙 -- 결과가 없으면 성공도 실패도 아니다).
- 실행 · 허가 · 네트워크는 여기 없다. 꼴만.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, fields

from .canonical import check_json, digest

SPEC = "action-contract/1"
INTENT_SCHEMA = "action-intent/1"
COMMAND_SCHEMA = "action-command/1"
OUTCOME_SCHEMA = "action-outcome/1"

AUTHOR_KINDS = ("rule", "llm", "human", "peer")
POLICY_REF = re.compile(r"^[^@\s]+@[^@\s]+$")          # "<정책 이름>@<판본>"
INTENT_ID = re.compile(r"^int-[0-9a-f]{16}$")
COMMAND_ID = re.compile(r"^cmd-[0-9a-f]{16}$")
EXCEPTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")  # 예외 **종류 이름**만. 메시지는 싣지 않는다(L0 recorder 와 같다)


class ContractError(ValueError):
    """꼴에 맞지 않는다. `errors` 에 까닭 전부."""

    def __init__(self, form: str, errors: "list[str]"):
        self.errors = list(errors)
        super().__init__(f"{form}: {'; '.join(self.errors)}")


# ── 칸 검사 ────────────────────────────────────────────────────────────────

def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v) -> bool:
    return (_is_int(v) or isinstance(v, float)) and math.isfinite(v)


def _text(v, name, errs, nonempty=True, nullable=False):
    if v is None and nullable:
        return
    if not isinstance(v, str):
        errs.append(f"{name}: 문자열이 아니다 ({type(v).__name__})")
    elif nonempty and not v.strip():
        errs.append(f"{name}: 비었다")


def _match(v, pat, name, errs):
    if not isinstance(v, str) or not pat.match(v):
        errs.append(f"{name}: 꼴이 아니다 {v!r} (기대 {pat.pattern})")


def _args(v, errs):
    if not isinstance(v, dict):
        errs.append(f"args: 객체가 아니다 ({type(v).__name__})")
        return
    errs.extend(f"args: {e}" for e in check_json(v, "args"))


def _schema(v, want, errs):
    if v != want:
        errs.append(f"schema: {v!r} (기대 {want!r})")


# ── 공통 ───────────────────────────────────────────────────────────────────

class _Form:
    SCHEMA: str
    ID: "str | None" = None          # 내용 해시로 정해지는 id 칸 이름(없으면 None)
    ID_PREFIX: str = ""
    OPTIONAL: frozenset = frozenset()   # None 이면 몸(body)에서 빠지는 칸 -- 옛 해시를 지킨다

    def _errors(self) -> "list[str]":
        raise NotImplementedError

    def __post_init__(self):
        errs = self._errors()
        if errs:
            raise ContractError(type(self).__name__, errs)

    def body(self) -> dict:
        """id 를 뺀 칸 전부 -- 해시의 입력."""
        return {f.name: _plain(getattr(self, f.name)) for f in fields(self)
                if not (f.name in self.OPTIONAL and getattr(self, f.name) is None)}

    def digest(self) -> str:
        return digest(self.body())

    def to_dict(self) -> dict:
        d = self.body()
        if self.ID:
            d[self.ID] = f"{self.ID_PREFIX}{self.digest()}"
        return d

    @classmethod
    def from_dict(cls, d: dict):
        name = cls.__name__
        if not isinstance(d, dict):
            raise ContractError(name, [f"객체가 아니다 ({type(d).__name__})"])
        known = {f.name for f in fields(cls)} | ({cls.ID} if cls.ID else set())
        required = ({f.name for f in fields(cls)} - cls.OPTIONAL) | ({cls.ID} if cls.ID else set())
        errs = [f"모르는 칸 {k!r}" for k in sorted(set(d) - known, key=str)]
        errs += [f"빠진 칸 {k!r}" for k in sorted(required - set(d))]
        if errs:
            raise ContractError(name, errs)
        obj = cls(**{f.name: d[f.name] for f in fields(cls) if f.name in d})
        if cls.ID and d[cls.ID] != obj.to_dict()[cls.ID]:
            raise ContractError(name, [f"{cls.ID}: 내용과 맞지 않는다 ({d[cls.ID]!r} ≠ {obj.to_dict()[cls.ID]!r})"])
        return obj

    @property
    def id(self) -> "str | None":
        return self.to_dict()[self.ID] if self.ID else None


def _plain(v):
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


# ── ActionIntent ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ActionIntent(_Form):
    """**실행 요청 제안**이다. 실행이 아니다. 누가 냈든(규칙 · LLM · 사람) 같은 꼴."""
    dc_id: str                   # 이 결정이 본 DecisionContext 의 id
    policy: str                  # 표의 `policy@ver`. 칸 이름에 '@' 를 쓸 수 없어 칸은 `policy`, 값이 "<이름>@<판본>"
    action: str                  # ActionSpec(Model) 이름
    target: "str | None"         # 겨냥 실체. 겨냥이 없는 행동(STOP · ESCALATE 등)은 None
    args: dict
    rationale: str
    used_keys: tuple             # 결정이 쓴 DC 키. 집합이다 -- 정렬해 둔다(같은 집합 = 같은 해시)
    author_kind: str             # rule · llm · human · peer
    schema: str = INTENT_SCHEMA
    msg_id: "str | None" = None  # author_kind=peer 일 때 이 의도를 낳은 동료 메시지의 id. 그때만 필수, 그 밖엔 None(해시에서 빠진다)

    SCHEMA = INTENT_SCHEMA
    OPTIONAL = frozenset({"msg_id"})
    ID = "intent_id"
    ID_PREFIX = "int-"

    def __post_init__(self):
        if isinstance(self.used_keys, (list, tuple)) and all(isinstance(k, str) for k in self.used_keys):
            object.__setattr__(self, "used_keys", tuple(sorted(self.used_keys)))
        super().__post_init__()

    def _errors(self):
        e = []
        _schema(self.schema, INTENT_SCHEMA, e)
        _text(self.dc_id, "dc_id", e)
        _match(self.policy, POLICY_REF, "policy", e)
        _text(self.action, "action", e)
        _text(self.target, "target", e, nullable=True)
        _args(self.args, e)
        _text(self.rationale, "rationale", e, nonempty=False)
        if not isinstance(self.used_keys, tuple) or not all(isinstance(k, str) and k for k in self.used_keys):
            e.append("used_keys: 빈 것이 아닌 문자열의 목록이어야 한다")
        elif len(set(self.used_keys)) != len(self.used_keys):
            e.append("used_keys: 겹치는 키")
        if self.author_kind not in AUTHOR_KINDS:
            e.append(f"author_kind: {self.author_kind!r} (기대 {AUTHOR_KINDS})")
        if self.author_kind == "peer":
            # 동료 메시지는 그 자체로 행동이 되지 않는다: DC · 쓴 키 · 원 메시지가 없으면 디스패치 전에 거절
            _text(self.msg_id, "msg_id", e)
            if not self.used_keys:
                e.append("used_keys: author_kind=peer 는 비어 있으면 안 된다")
        elif self.msg_id is not None:
            e.append("msg_id: author_kind=peer 일 때만 쓴다")
        return e


# ── ActionCommand ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ActionCommand(_Form):
    """GUARD 가 허가한 실행 명령. 실행기는 이것만 받는다."""
    intent_id: str               # 어느 의도에서 나왔나
    decision_ref: str            # **표에 없던 칸.** 이 명령을 낸 결정 기록(MS DecisionRecord)의 id. L0 action.dispatch.decision_ref 로 간다
    action: str                  # 의도의 action 과 다를 수 있다(GUARD 의 SAFE_ACTION). 그래서 따로 둔다
    target: "str | None"
    args: dict
    issued_at: float             # unix_ms
    deadline: "float | None"     # unix_ms. 없으면 None(실행 기한을 두지 않음). 검증 시간 창은 ActionSpec 의 것이다(BD-31)
    schema: str = COMMAND_SCHEMA

    SCHEMA = COMMAND_SCHEMA
    ID = "command_id"
    ID_PREFIX = "cmd-"

    def _errors(self):
        e = []
        _schema(self.schema, COMMAND_SCHEMA, e)
        _match(self.intent_id, INTENT_ID, "intent_id", e)
        _text(self.decision_ref, "decision_ref", e)
        _text(self.action, "action", e)
        _text(self.target, "target", e, nullable=True)
        _args(self.args, e)
        if not _is_num(self.issued_at) or self.issued_at < 0:
            e.append(f"issued_at: 0 이상 유한한 수(unix_ms)가 아니다 ({self.issued_at!r})")
        if self.deadline is not None:
            if not _is_num(self.deadline):
                e.append(f"deadline: 유한한 수(unix_ms)가 아니다 ({self.deadline!r})")
            elif _is_num(self.issued_at) and self.deadline <= self.issued_at:
                e.append(f"deadline: issued_at 보다 늦어야 한다 ({self.deadline!r} ≤ {self.issued_at!r})")
        return e


# ── ActionOutcome ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ActionOutcome(_Form):
    """실행기가 본 결과. L0 `action.result` 의 칸과 같다(`l0map.RESULT`). None = 못 봤다. 판정(성공 · 실패)은 없다."""
    command_id: str              # L0 action_ref
    is_error: "bool | None" = None
    exit_code: "int | None" = None
    status_code: "int | None" = None
    exception: "str | None" = None       # 표의 `error`. L0 이름을 그대로 쓴다 -- 같은 것에 이름 둘을 두지 않는다
    output_chars: "int | None" = None
    elapsed_ms: "float | None" = None
    schema: str = OUTCOME_SCHEMA

    SCHEMA = OUTCOME_SCHEMA

    def _errors(self):
        e = []
        _schema(self.schema, OUTCOME_SCHEMA, e)
        _match(self.command_id, COMMAND_ID, "command_id", e)
        if self.is_error is not None and not isinstance(self.is_error, bool):
            e.append(f"is_error: bool 이 아니다 ({self.is_error!r})")
        for k in ("exit_code", "status_code"):
            v = getattr(self, k)
            if v is not None and not _is_int(v):
                e.append(f"{k}: int 가 아니다 ({v!r})")
        if self.exception is not None:
            _match(self.exception, EXCEPTION_NAME, "exception", e)
        if self.output_chars is not None and (not _is_int(self.output_chars) or self.output_chars < 0):
            e.append(f"output_chars: 0 이상 int 가 아니다 ({self.output_chars!r})")
        if self.elapsed_ms is not None and (not _is_num(self.elapsed_ms) or self.elapsed_ms < 0):
            e.append(f"elapsed_ms: 0 이상 유한한 수가 아니다 ({self.elapsed_ms!r})")
        return e


FORMS = (ActionIntent, ActionCommand, ActionOutcome)
