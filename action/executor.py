"""실행기 접점 -- ActionCommand → (처리기) → ActionOutcome + L0 action.dispatch / action.result. (CMD-A3 E1 설계안의 증명)

    execute(command, model, handlers, recorder=None, mode="shadow", mono=None) -> Execution

모드는 둘이다(docs/EXECUTOR.md §2):
    shadow   처리기를 부르지 않고 L0 에도 적지 않는다. 명령이 실행될 수 **있었는지**(행동이 모형에 있나 · 처리기가 붙었나)와
             L0 에 적었을 칸(`would_dispatch`)만 돌려준다. 실제 실행은 런타임이 지금 길대로 한다 -- 대조용
    execute  처리기를 부르고 `recorder.action(..., action_ref=command_id)` 로 L0 에 적는다. 한 사실은 한 사건(BD-97 Q3)
dry-run 은 모드가 아니다: execute 에 **바깥에 닿지 않는 처리기**(MS 의 effect 틀 같은)를 붙인 것이다. 실행기는 처리기가
진짜인지 모른다 -- 모의 여부는 실행(run)의 속성이다(MS RunRecord.simulated).

처리기 약속(MS 의 도구 handler 를 감싼 것):
    handler(target, args) -> {"observations": [...], "is_error"?: bool, "exit_code"?: int, "status_code"?: int, "output"?: str}
    observations 는 **불투명**하다 -- 실행기는 읽지 않고 돌려준다(런타임이 자기 상태 관리자에 넣는다, PC19 G2).
    빠진 결과 칸은 못 본 것이다. 기본값으로 메우지 않는다.

닫힌 쪽: 모형에 없는 행동 · 처리기 없음 · 모르는 모드는 **실행하지 않는다**(L0 에도 적지 않는다).
판정(허가 · 사전조건 · 위험)은 여기 없다 -- Guard 가 낸 명령만 온다는 것이 전제다.
"""
from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass, field

from .forms import ActionCommand, ActionOutcome, ContractError
from .spec import ActionModel

SHADOW, EXECUTE = "shadow", "execute"
MODES = (SHADOW, EXECUTE)
REPORTED = ("observations", "is_error", "exit_code", "status_code", "output")
ARGS_PARAM = "args"     # Recorder.action 이 인자를 받는 칸 이름(T17). T17 이 다른 이름을 고르면 여기 하나만 고친다

# 실행하지 않은 까닭(닫힌 목록)
UNKNOWN_ACTION, NO_HANDLER, BAD_MODE = "UNKNOWN_ACTION", "NO_HANDLER", "BAD_MODE"


@dataclass(frozen=True)
class Execution:
    command_id: str
    mode: str
    executed: bool                            # 처리기를 불렀나
    refused: "str | None" = None              # 실행하지 않은 까닭(닫힌 목록). 실행했으면 None
    would_dispatch: dict = field(default_factory=dict)   # L0 action.dispatch 에 적을(적은) 칸. 겨냥은 평문 -- 해시는 Recorder 가 한다
    outcome: "ActionOutcome | None" = None    # execute 에서만
    observations: list = field(default_factory=list)     # 처리기가 돌려준 관측(불투명)
    raised: "BaseException | None" = None     # 처리기가 던진 예외(런타임이 메시지를 자기 관측으로 쓸 수 있게). L0 에는 종류 이름만

    def to_dict(self) -> dict:
        """원장에 적을 꼴(JSON). 관측의 내용과 예외 메시지는 싣지 않는다 -- 관측은 런타임의 상태 관리자로, 예외는 종류 이름만."""
        return {"command_id": self.command_id, "mode": self.mode, "executed": self.executed, "refused": self.refused,
                "would_dispatch": dict(self.would_dispatch),
                "outcome": self.outcome.to_dict() if self.outcome is not None else None,
                "observations": len(self.observations), "raised": type(self.raised).__name__ if self.raised else None}


def _plan(command: ActionCommand) -> dict:
    return {"action_ref": command.id, "decision_ref": command.decision_ref, "action_type": command.action,
            "target": command.target}


def execute(command: ActionCommand, model: ActionModel, handlers: dict, recorder=None, mode: str = SHADOW,
            mono=None) -> Execution:
    """mono: 단조 시계(ms). 없으면 recorder.mono, 그것도 없으면 time.monotonic×1000."""
    if not isinstance(command, ActionCommand):
        raise TypeError(f"command: ActionCommand 가 아니다 ({type(command).__name__})")
    if not isinstance(model, ActionModel):
        raise TypeError(f"model: ActionModel 이 아니다 ({type(model).__name__})")
    plan = _plan(command)
    if mode not in MODES:
        return Execution(command.id, str(mode), False, BAD_MODE, plan)
    if model.get(command.action) is None:
        return Execution(command.id, mode, False, UNKNOWN_ACTION, plan)
    handler = handlers.get(command.action)
    if handler is None:
        return Execution(command.id, mode, False, NO_HANDLER, plan)
    if mode == SHADOW:
        return Execution(command.id, mode, False, None, plan)

    clock = mono or getattr(recorder, "mono", None) or (lambda: time.monotonic() * 1000)     # 언제나 ms
    vals: dict = {}
    obs: list = []
    raised = None
    if recorder is None:
        ctx = _NoL0()
    else:
        kw = {"decision_ref": command.decision_ref, "target": command.target, "action_ref": command.id}
        if _takes(recorder.action, ARGS_PARAM):  # T17: 인자 서명은 Telemetry 가 짓는다(평문은 L0 에 남지 않는다). 없으면 넘기지 않는다
            kw[ARGS_PARAM] = dict(command.args)
        ctx = recorder.action(command.action, **kw)
    t0 = clock()
    try:
        with ctx as h:
            rep = handler(command.target, dict(command.args))
            bad = _report_errors(rep)
            if bad:
                raise ContractError("handler", bad)
            obs = list(rep.get("observations") or [])
            vals = {k: rep[k] for k in ("is_error", "exit_code", "status_code") if rep.get(k) is not None}
            if rep.get("output") is not None:
                vals["output_chars"] = len(rep["output"])
            h.result(output=rep.get("output"), **{k: v for k, v in vals.items() if k != "output_chars"})
    except Exception as e:                    # Recorder 가 exception · is_error 를 이미 적었다(recorder.py). 여기서는 결과에만
        raised = e
        vals = {"is_error": True, "exception": type(e).__name__}    # 처리기가 돌려준 관측은(있으면) 사실이라 버리지 않는다
    outcome = ActionOutcome(command_id=command.id, elapsed_ms=round(clock() - t0, 3), **vals)
    return Execution(command.id, mode, True, None, plan, outcome, obs, raised)


def _report_errors(rep) -> "list[str]":
    if not isinstance(rep, dict):
        return [f"처리기 결과가 dict 가 아니다 ({type(rep).__name__})"]
    e = [f"모르는 칸 {k!r}" for k in rep if k not in REPORTED]
    if not isinstance(rep.get("observations", []), list):
        e.append("observations: 목록이 아니다")
    if rep.get("is_error") is not None and not isinstance(rep["is_error"], bool):
        e.append("is_error: bool 이 아니다")
    for k in ("exit_code", "status_code"):
        v = rep.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
            e.append(f"{k}: int 가 아니다")
    if rep.get("output") is not None and not isinstance(rep["output"], str):
        e.append("output: 문자열이 아니다")
    return e


def _takes(fn, name: str) -> bool:
    try:
        ps = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return name in ps or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in ps.values())


class _NoL0:
    """L0 를 안 쓸 때(MS NullRecorder 자리). 결과 손잡이도 아무것도 안 한다."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def result(self, output=None, **kw):
        pass


def ms_handler(tool_run) -> "callable":
    """MS 도구(ToolSpec.run: (target, args) -> [관측 dict]) → 처리기 약속. pipeline.py:146-148 과 같은 읽기:
    관측 가운데 signal == "tool_error" 가 있으면 is_error, 출력은 관측의 JSON."""
    def handler(target, args):
        obs = list(tool_run(target, args) or [])
        return {"observations": obs, "is_error": any(o.get("signal") == "tool_error" for o in obs),
                "output": json.dumps(obs, ensure_ascii=False, default=str)}
    return handler
