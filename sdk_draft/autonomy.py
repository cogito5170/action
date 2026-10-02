"""SDK 입구 시제품(CMD-A7 · S1, BD-119) -- docs/SDK.md §1 의 모양을 증명하려는 **초안**이다. 집은 `cogito5170/rlo-SDK` 다(SDK.md §6) -- S2 에서 그리로 옮긴다.

`action` 패키지 밖에 둔다: 이것은 MS(Policy) · DC · guard · health 를 import 하므로, action 안에 두면 action 의 규칙
("표준 라이브러리만" · "Action 은 Policy 를 import 하지 않는다", BASELINE.md:227)을 어긴다.

    a = Autonomy.from_spec(spec, observations, actions=[...], llm=provider)    # 세계 · 행동 · LLM 은 반드시 받는다
    a.open_session("s", {"token_budget": 1000})
    out = a.handle("srv07 을 throttle", queries=spec["queries"])               # 결정 → Guard → 실행기 → VERIFY

기본으로 채우는 것:
    DC 길    MSStateReader(목적 context_runtime). 의도 · Guard · 실행기 · VERIFY 는 DC 길에서만 돈다(ms/intent.py:48-52 ·
             runtime.py:152) -- 그래서 SDK 는 snapshot 길을 내놓지 않는다(BD-114 (2) 와 같은 쪽)
    guard_mode "shadow"(BD-118). "enforce" 는 guard 가 있어야 선다
    L0       끔. `l0=` 경로나 sink 를 주면 켠다
부작용: 처리기를 주지 않은 행동은 MS 의 effect 틀(모의)로 돈다. 이 모듈 자신은 파일 · 네트워크 · 환경을 건드리지 않는다
(원장 `ledger=` 를 주지 않으면 원장도 쓰지 않는다).
"""
from __future__ import annotations

import copy
import dataclasses

SDK_DRAFT = "rlo-sdk/0-draft"   # 집 cogito5170/rlo-SDK · 배포 rlo-sdk · import rlo (SDK.md §6)


@dataclasses.dataclass
class Result:
    """handle 의 결과. MS Runtime.handle 의 dict(runtime.py:255-256)를 그대로 싣고, 자주 보는 것만 이름으로 꺼낸다."""
    raw: dict

    @property
    def outcome(self) -> str:
        return self.raw["result"]["outcome"]

    @property
    def decision_id(self) -> str:
        return self.raw["decision"]["id"]

    @property
    def executions(self) -> list:
        return self.raw.get("executions", [])

    @property
    def guards(self) -> list:
        return self.raw.get("guards", [])

    @property
    def verifications(self) -> list:
        return self.raw.get("verifications", [])


class Autonomy:
    """일곱 패키지를 조립하는 입구 하나. MS Runtime 이 이미 조립자다 -- 이 층은 꽂는 자리를 한 곳에 모으고 DC 길을 기본으로 묶는다."""

    def __init__(self, world, *, actions, llm, purpose: str = "context_runtime", guard_mode: str = "shadow",
                 grants=(), l0=None, ledger: "str | None" = None, run_state=None):
        from dc import DecisionContextBuilder, MSGraphSource, MSStateReader, MSUsageSource
        from ms import usage_model as U
        from ms.query import StateQuery, run_query
        from ms.runtime import Runtime
        from ms.tools import ToolRegistry

        registry = actions if isinstance(actions, ToolRegistry) else ToolRegistry(copy.deepcopy(list(actions)))
        kw = {"l0_sink": l0} if (l0 is not None and not isinstance(l0, str)) else ({"l0_ledger": l0} if l0 else {})
        self.runtime = Runtime(world, registry, {"llm": llm}, grants=grants, ledger_path=ledger, guard_mode=guard_mode,
                               run_state=run_state, **kw)
        builder = DecisionContextBuilder([MSUsageSource(self.runtime.um, U.MODEL_VERSION),
                                          MSGraphSource(world, run_query, StateQuery.from_dict)])
        self.runtime.state_reader = MSStateReader(builder, purpose)
        self.session: "str | None" = None

    @classmethod
    def from_spec(cls, spec: dict, observations=(), *, clock=None, actions=None, **kw) -> "Autonomy":
        """MS 세계 명세(dict) + 관측(dict 목록)에서. actions 를 안 주면 명세의 `tools` 를 쓴다(handler 없음 = effect 틀)."""
        from ms.cli import clock_for
        from ms.manager import StateManager
        world = StateManager.from_spec(spec, clock=clock or clock_for(spec))
        for o in observations:
            world.ingest(o)
        return cls(world, actions=spec["tools"] if actions is None else actions, **kw)

    def open_session(self, name: str, budgets: dict) -> str:
        self.session = name
        return self.runtime.open_session(name, budgets)

    def handle(self, task: str, queries=(), session: "str | None" = None, **request) -> Result:
        s = session or self.session
        if s is None:
            raise ValueError("세션이 없다 -- open_session 먼저")
        return Result(self.runtime.handle({"session": s, "task": task, "queries": list(queries), **request}))

    def close_windows(self) -> list:
        """창이 닫힌 VERIFY 를 마감한다(handle 마다 처음에도 돈다, runtime.py:147)."""
        return self.runtime.close_windows()

    @staticmethod
    def versions() -> dict:
        """동결된 계약의 판본 -- 공개 경계(SDK.md §3). 패키지가 없으면 None."""
        out = {"sdk": SDK_DRAFT}
        try:
            from action import SPEC, SPEC_SCHEMA, MODEL_SCHEMA
            out.update({"action-contract": SPEC, "action-spec": SPEC_SCHEMA, "action-model": MODEL_SCHEMA})
        except ImportError:
            pass
        for key, mod, attr in (("guard-result", "guard.forms", "GUARD_SCHEMA"),
                               ("validation-result", "guard.forms", "VALIDATION_SCHEMA"),
                               ("verification-record", "health.verification", "SCHEMA"),
                               ("l0-telemetry", "telemetry.catalog", "SPEC")):
            try:
                out[key] = getattr(__import__(mod, fromlist=[attr]), attr)
            except (ImportError, AttributeError):
                out[key] = None
        return out
