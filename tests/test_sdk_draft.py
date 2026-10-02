"""SDK 시제품(sdk_draft/, CMD-A7 · S1) -- 입구 한 바퀴와 훅 어댑터. 옆 저장소(MS · DC · guard · health · Telemetry)가 있을 때."""
import asyncio
import copy
import io
import json
import pathlib
import sys
import unittest

from action.spec import ActionModel, ActionSpec
from tests import siblings

DRAFT = pathlib.Path(__file__).resolve().parent.parent / "sdk_draft"
NEED = (("ms", "ms"), ("dc", "dc"), ("guard", "guard"), ("health", "health"), ("telemetry", "telemetry"))


def _paths():
    roots = [siblings.repo(n, p) for n, p in NEED]
    if any(r is None for r in roots):
        return None
    for r in [DRAFT, *roots]:
        if str(r) not in sys.path:
            sys.path.insert(0, str(r))
    return roots


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class Loop(unittest.TestCase):
    """설계안의 입구 모양으로 예시 세계에서 한 바퀴: 결정 → Guard → 실행기 → VERIFY. 부작용 없음(원장 없음 · L0 는 메모리)."""

    def setUp(self):
        roots = _paths()
        if roots is None:
            self.skipTest("옆 저장소(MS · DC · guard · health · Telemetry)를 찾지 못함 -- <이름>_REPO")
        ms = roots[0]
        self.spec = json.loads((ms / "ms/examples/datacenter.json").read_text(encoding="utf-8"))
        self.obs = [json.loads(l) for l in (ms / "ms/examples/datacenter_telemetry.jsonl").read_text(encoding="utf-8").splitlines() if l]
        self.tools = copy.deepcopy(self.spec["tools"])
        for t in self.tools:
            if t["name"] == "throttle":
                t.update(postcondition=[{"entity": "$target", "pred": ["throttled", "==", True]}], window_ms=60000)

    def run_once(self, mode, **kw):
        from autonomy import Autonomy
        from ms.providers import make_provider
        from telemetry.ledger import MemorySink
        sink = MemorySink()
        a = Autonomy.from_spec(self.spec, self.obs, clock=Clock(self.spec["now"]), actions=self.tools,
                               llm=make_provider("sim-claude"), guard_mode=mode, l0=sink, **kw)
        a.open_session("s", {"token_budget": 1000})
        return a, a.handle("srv07 을 throttle", queries=self.spec["queries"]), sink

    def test_one_turn_both_modes(self):
        for mode in ("shadow", "enforce"):
            with self.subTest(mode):
                a, r, sink = self.run_once(mode)
                self.assertEqual(r.outcome, "executed")
                self.assertEqual([g["guard"]["verdict"] for g in r.guards], ["ALLOW"])
                self.assertEqual((a.runtime.guard_mode, r.guards[0]["guard"]["mode"]), (mode, mode))
                (x,) = r.executions
                self.assertEqual((x["command"]["action"], x["command"]["target"]), ("throttle", "srv07"))
                self.assertEqual(x["command"]["decision_ref"], r.decision_id)
                (v,) = r.verifications
                self.assertEqual((v["record"]["result"], v["record"]["reason"]), ("VERIFIED", "MET"))
                types = [e["type"] for e in sink.events]
                self.assertEqual([t for t in types if t.startswith(("action.", "tool."))], ["action.dispatch", "action.result"])
                disp = next(e for e in sink.events if e["type"] == "action.dispatch")
                self.assertEqual(disp["data"]["action_ref"], x["command"]["command_id"])
                self.assertIsNone(a.runtime.ledger_path)                       # 원장을 주지 않으면 쓰지 않는다

    def test_dc_path_is_the_default(self):
        a, r, _ = self.run_once("shadow")
        self.assertEqual(r.raw["decision"]["state_source"]["kind"], "state_reader")
        self.assertTrue(r.raw["decision"]["state_source"]["id"].startswith("dc-"))

    def test_versions_are_the_frozen_contracts(self):
        from autonomy import Autonomy
        v = Autonomy.versions()
        self.assertEqual({k: v[k] for k in ("action-contract", "action-spec", "action-model", "guard-result",
                                            "validation-result", "verification-record", "l0-telemetry")},
                         {"action-contract": "action-contract/1", "action-spec": "action-spec/1",
                          "action-model": "action-model/1", "guard-result": "guard-result/1",
                          "validation-result": "validation-result/1", "verification-record": "verification-record/1",
                          "l0-telemetry": "l0-telemetry/1"})

    def test_handle_needs_a_session(self):
        from autonomy import Autonomy
        from ms.providers import make_provider
        a = Autonomy.from_spec(self.spec, self.obs, clock=Clock(self.spec["now"]), llm=make_provider("sim-claude"))
        with self.assertRaises(ValueError):
            a.handle("x")


# ── 훅 어댑터 ────────────────────────────────────────────────────────────────

BASH = ActionSpec("Bash", "1", None, params={"command": {"type": "string"},
                                              "description": {"type": "string", "required": False},
                                              "timeout": {"type": "number", "required": False},
                                              "run_in_background": {"type": "bool", "required": False}},
                  risk="external")
PRE_INPUT = {   # code.claude.com/docs/en/hooks.md "PreToolUse input" 의 예 그대로
    "session_id": "abc123", "transcript_path": "/home/user/.claude/projects/.../transcript.jsonl",
    "cwd": "/home/user/my-project", "permission_mode": "default", "hook_event_name": "PreToolUse",
    "tool_name": "Bash", "tool_input": {"command": "npm test", "description": "Run test suite", "timeout": 120000,
                                        "run_in_background": False},
    "tool_use_id": "toolu_01ABC123..."}
POST_FAIL_INPUT = {  # 같은 문서 "PostToolUseFailure input" 의 예 그대로
    "session_id": "abc123", "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
    "cwd": "/Users/...", "permission_mode": "default", "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
    "tool_input": {"command": "npm test", "description": "Run test suite"}, "tool_use_id": "toolu_01ABC123...",
    "error": "Exit code 1\nError: Cannot find module 'express'", "is_interrupt": False, "duration_ms": 4187}


class Hooks(unittest.TestCase):
    def setUp(self):
        self.g = siblings.load("guard", "guard")
        if self.g is None:
            self.skipTest("guard 를 찾지 못함 -- GUARD_REPO")
        if str(DRAFT) not in sys.path:
            sys.path.insert(0, str(DRAFT))
        import hooks
        self.H = hooks
        self.records = []

    def adapter(self, mode, grants=(), judge=None, observe=None):
        g = self.g
        model = g.GuardModel.from_action_model(ActionModel("cc-tools-1", (BASH,)), grants=grants)
        dc = g.DCView("dc-hook-test", offers={"Bash": [None]}, seen={})
        state = g.StateView({})
        judge = judge or (lambda it: g.evaluate(it, dc, state, model, mode)[1])
        return self.H.HookAdapter(judge, dc_id_of=lambda d: "dc-hook-test", policy="cc-hook@0", mode=mode,
                                  record=lambda k, d: self.records.append((k, d)), observe=observe)

    def test_enforce_denies_in_the_documented_shape(self):
        out = self.adapter("enforce").handle(PRE_INPUT)                   # 허가 없는 external → A7
        self.assertEqual(set(out), {"hookSpecificOutput"})
        hso = out["hookSpecificOutput"]
        self.assertEqual((hso["hookEventName"], hso["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("A7", hso["permissionDecisionReason"])
        self.assertEqual(self.records[0][1]["result"]["verdict"], "DENY")

    def test_allow_never_widens_permission(self):
        out = self.adapter("enforce", grants=("Bash",)).handle(PRE_INPUT)
        self.assertEqual(out, {})                                            # "allow" 를 내지 않는다
        self.assertEqual(self.records[0][1]["result"]["verdict"], "ALLOW")

    def test_shadow_records_but_never_blocks(self):
        out = self.adapter("shadow").handle(PRE_INPUT)
        self.assertEqual(out, {})
        self.assertEqual(self.records[0][1]["result"]["verdict"], "DENY")

    def test_unknown_tool_argument_is_a4(self):
        bad = dict(PRE_INPUT, tool_input={"command": "ls", "dangerously": True})
        out = self.adapter("enforce", grants=("Bash",)).handle(bad)
        self.assertIn("A4", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_judge_error_closes_only_in_enforce(self):
        def boom(it):
            raise RuntimeError("secret detail")
        out = self.adapter("enforce", judge=boom).handle(PRE_INPUT)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecisionReason"], "guard error: RuntimeError")
        self.assertEqual(self.adapter("shadow", judge=boom).handle(PRE_INPUT), {})

    def test_post_hooks_only_observe(self):
        seen = []
        a = self.adapter("enforce", observe=seen.append)
        post = dict(PRE_INPUT, hook_event_name="PostToolUse", tool_response={"stdout": "ok"}, duration_ms=12)
        self.assertEqual(a.handle(post), {})
        self.assertEqual(a.handle(POST_FAIL_INPUT), {})
        self.assertEqual([d["hook_event_name"] for d in seen], ["PostToolUse", "PostToolUseFailure"])
        self.assertEqual(self.records, [])                                   # 실행 뒤 훅은 판정하지 않는다

    def test_command_hook_and_sdk_callback(self):
        a = self.adapter("enforce")
        out = io.StringIO()
        self.assertEqual(self.H.run_command_hook(a, io.StringIO(json.dumps(PRE_INPUT)), out), 0)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")
        got = asyncio.run(a.callback(PRE_INPUT, "toolu_01ABC123...", None))
        self.assertEqual(got["hookSpecificOutput"]["permissionDecision"], "deny")
        empty = io.StringIO()
        self.H.run_command_hook(self.adapter("shadow"), io.StringIO(json.dumps(PRE_INPUT)), empty)
        self.assertEqual(empty.getvalue(), "")                               # 허락이면 아무것도 쓰지 않는다

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.H.HookAdapter(lambda it: None, dc_id_of=lambda d: "x", policy="p@0", mode="audit")


if __name__ == "__main__":
    unittest.main()
