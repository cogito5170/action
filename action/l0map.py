"""행동 꼴 ↔ L0 사건 대응표. 실행기는 이 표대로 L0 사건 칸을 채운다(L0 꼴 · Recorder 는 Telemetry 의 것이다).

    ActionCommand  ─(실행 시작)─►  action.dispatch
    ActionOutcome  ─(실행 끝)───►  action.result

`L0_FIELDS` 는 Telemetry 의 `telemetry/catalog.py` EVENTS 를 **베낀 것**이다(아래 커밋). 이 저장소는 Telemetry 를 import 하지 않는다
(표준 라이브러리만, OQ-19). 베낀 것이 흘러가지 않았는지는 `tests/test_l0map.py` 가 Telemetry 를 찾으면 대조한다.
"""
from __future__ import annotations

L0_SOURCE = "cogito5170/Telemetry@89d2887768a1f230860ea6323870a747fd4323ef telemetry/catalog.py"   # CMD-T17: action.dispatch.args_sig

L0_FIELDS = {
    "action.dispatch": ("action_ref", "decision_ref", "action_type", "target", "args_sig"),
    "action.result": ("action_ref", "is_error", "exit_code", "status_code", "exception", "output_chars", "elapsed_ms"),
}

# L0 칸 → (꼴의 칸, 옮기는 법)
#   copy   그대로
#   hash   Telemetry 의 열쇠 해시(HMAC-SHA256 12 hex, `telemetry.hashing.Hasher`) 로만 -- 겨냥 글은 L0 에 남기지 않는다
#   actual 실행기가 **실제로 실행한** 행동 이름. 보통 command.action 과 같다. 다르면(실행기가 바꿔 실행) 실제 것을 적는다
#   sig    Telemetry 가 짓는 서명(`tool_sig` 방식: 행동 이름 + 인자 정규형의 열쇠 해시). 실행기는 `Recorder.action(args=…)` 로
#          인자를 넘기기만 한다(T17). 평문은 L0 에 남지 않는다
DISPATCH = {
    "action_ref": ("ActionCommand.command_id", "copy"),
    "decision_ref": ("ActionCommand.decision_ref", "copy"),
    "action_type": ("ActionCommand.action", "actual"),
    "target": ("ActionCommand.target", "hash"),
    "args_sig": ("ActionCommand.args", "sig"),
}
RESULT = {
    "action_ref": ("ActionOutcome.command_id", "copy"),
    "is_error": ("ActionOutcome.is_error", "copy"),
    "exit_code": ("ActionOutcome.exit_code", "copy"),
    "status_code": ("ActionOutcome.status_code", "copy"),
    "exception": ("ActionOutcome.exception", "copy"),
    "output_chars": ("ActionOutcome.output_chars", "copy"),
    "elapsed_ms": ("ActionOutcome.elapsed_ms", "copy"),
}

# 꼴에 있지만 L0 로 가지 않는 칸과 그 까닭. 빠진 칸은 이 둘 중 하나다 -- 어디에도 없으면 시험이 빨개진다
NOT_IN_L0 = {
    "ActionIntent.*": "의도는 결정이다 -- L0 는 결정을 싣지 않는다(TELEMETRY.md 6 · 7 절). 원장(MS DecisionRecord)에 있다",
    "ActionCommand.intent_id": "결정 쪽 식별자. L0 는 decision_ref 하나로만 잇는다",
    "ActionCommand.issued_at": "L0 봉투의 `at` 이 dispatch 사건을 본 시각이다",
    "ActionCommand.deadline": "우리 기한은 L0 에 없다(THRESHOLD_WORDS). 실행기가 선언한 기한으로 싣자면 declared 칸을 요청한다(요청 R1)",
    "ActionCommand.schema": "꼴 판본. L0 봉투는 자기 spec 을 갖는다",
    "ActionOutcome.schema": "꼴 판본. L0 봉투는 자기 spec 을 갖는다",
}


def dispatch_data(command, action_type: str, hasher, sig=None) -> dict:
    """ActionCommand → L0 `action.dispatch` 의 data 칸. `hasher` 는 Telemetry 의 Hasher(문자열 → 12 hex),
    `sig` 는 Telemetry 의 서명 함수 `(이름, 인자) -> str`(없으면 args_sig 는 못 봄). 서명 방식은 여기서 다시 짓지 않는다."""
    return {"action_ref": command.id, "decision_ref": command.decision_ref, "action_type": action_type,
            "target": None if command.target is None else f"#{hasher(command.target)}",
            "args_sig": None if sig is None else sig(action_type, dict(command.args))}


def result_data(outcome) -> dict:
    """ActionOutcome → L0 `action.result` 의 data 칸. None 은 그대로 None(L0 에서 unobserved)."""
    return {"action_ref": outcome.command_id, **{k: getattr(outcome, k) for k in L0_FIELDS["action.result"][1:]}}
