import unittest

from action import ContractError
from action.executor import (BAD_MODE, EXECUTE, NO_HANDLER, SHADOW, UNKNOWN_ACTION, Execution, execute, ms_handler)
from action.forms import ActionCommand
from action.spec import ActionModel, ActionSpec
from tests import siblings

MODEL = ActionModel("m1", (ActionSpec("throttle", "1", "Server", risk="local"),
                           ActionSpec("escalate", "1", None, risk="external")))


def command(action="throttle", target="srv1", args=None):
    return ActionCommand(intent_id="int-" + "1" * 16, decision_ref="dec-00112233aabbccdd", action=action, target=target,
                         args={"level": 2} if args is None else args, issued_at=1_000_000.0, deadline=None)


class Spy:
    def __init__(self, rep=None, exc=None):
        self.calls, self.rep, self.exc = [], rep, exc

    def __call__(self, target, args):
        self.calls.append((target, args))
        if self.exc:
            raise self.exc
        return self.rep


class FakeRecorder:
    """Telemetry Recorder.action 의 모양만(사건 목록을 남긴다). 진짜 Recorder 대조는 아래 WithTelemetry."""
    def __init__(self):
        self.events, self.t = [], 0.0

    def mono(self):
        self.t += 5.0
        return self.t

    def action(self, action_type, decision_ref=None, target=None, action_ref=None):
        rec = self

        class Ctx:
            vals = {}

            def __enter__(self):
                rec.events.append(("action.dispatch", dict(action_ref=action_ref, decision_ref=decision_ref,
                                                           action_type=action_type, target=target)))
                return self

            def result(self, output=None, **kw):
                self.vals.update(kw, **({"output_chars": len(output)} if output is not None else {}))

            def __exit__(self, et, e, tb):
                if e is not None:
                    self.vals.setdefault("exception", type(e).__name__)
                    self.vals.setdefault("is_error", True)
                rec.events.append(("action.result", dict(action_ref=action_ref, **self.vals)))
                return False
        return Ctx()


class FakeRecorderT17(FakeRecorder):
    """T17 뒤의 모양: action 이 인자(args)를 받는다. 받은 것을 남긴다."""
    def action(self, action_type, decision_ref=None, target=None, action_ref=None, args=None):
        self.got_args = args
        return super().action(action_type, decision_ref, target, action_ref)


class Refusals(unittest.TestCase):
    def test_closed_side(self):
        for cmd, handlers, mode, why in ((command("reboot"), {"reboot": Spy({})}, EXECUTE, UNKNOWN_ACTION),
                                         (command(), {}, EXECUTE, NO_HANDLER),
                                         (command(), {"throttle": Spy({})}, "enforce", BAD_MODE)):
            with self.subTest(why):
                rec = FakeRecorder()
                x = execute(cmd, MODEL, handlers, rec, mode)
                self.assertEqual((x.executed, x.refused, x.outcome), (False, why, None))
                self.assertEqual(rec.events, [])                    # 실행하지 않은 것은 L0 에 없다
                for h in handlers.values():
                    self.assertEqual(h.calls, [])

    def test_type_errors(self):
        with self.assertRaises(TypeError):
            execute(command().to_dict(), MODEL, {})
        with self.assertRaises(TypeError):
            execute(command(), {"specs": []}, {})


class Shadow(unittest.TestCase):
    def test_no_call_no_event(self):
        h, rec = Spy({"observations": []}), FakeRecorder()
        x = execute(command(), MODEL, {"throttle": h}, rec)          # 기본은 shadow
        self.assertEqual((x.mode, x.executed, x.refused, x.outcome), (SHADOW, False, None, None))
        self.assertEqual(h.calls, [])
        self.assertEqual(rec.events, [])
        self.assertEqual(x.would_dispatch, {"action_ref": command().id, "decision_ref": "dec-00112233aabbccdd",
                                            "action_type": "throttle", "target": "srv1"})


class Execute(unittest.TestCase):
    def test_one_fact_one_pair(self):
        obs = [{"signal": "throttle_ack", "value": True}]
        h, rec = Spy({"observations": obs, "is_error": False, "output": "abc"}), FakeRecorder()
        x = execute(command(), MODEL, {"throttle": h}, rec, EXECUTE)
        self.assertEqual(h.calls, [("srv1", {"level": 2})])
        self.assertEqual([t for t, _ in rec.events], ["action.dispatch", "action.result"])
        disp, res = rec.events[0][1], rec.events[1][1]
        self.assertEqual(disp, x.would_dispatch)
        self.assertEqual(res, {"action_ref": command().id, "is_error": False, "output_chars": 3})
        o = x.outcome
        self.assertEqual((o.command_id, o.is_error, o.output_chars, o.exit_code, o.exception, o.elapsed_ms),
                         (command().id, False, 3, None, None, 5.0))
        self.assertEqual(x.observations, obs)                       # 불투명 -- 그대로 돌려준다
        self.assertIsNone(x.raised)

    def test_unobserved_stays_none(self):
        x = execute(command(), MODEL, {"throttle": Spy({"observations": []})}, FakeRecorder(), EXECUTE)
        self.assertIsNone(x.outcome.is_error)                       # 보고하지 않은 결과를 성공으로 메우지 않는다
        self.assertIsNone(x.outcome.output_chars)

    def test_exception_is_observed_by_type_only(self):
        rec = FakeRecorder()
        x = execute(command(), MODEL, {"throttle": Spy(exc=TimeoutError("secret path /x"))}, rec, EXECUTE)
        self.assertEqual((x.outcome.is_error, x.outcome.exception), (True, "TimeoutError"))
        self.assertEqual(rec.events[1][1]["exception"], "TimeoutError")
        self.assertNotIn("secret", str(x.outcome.to_dict()))
        self.assertIsInstance(x.raised, TimeoutError)               # 메시지는 런타임이 자기 관측으로 쓸 수 있다
        self.assertEqual(x.observations, [])

    def test_bad_report_is_an_error_not_a_success(self):
        for rep in (None, {"observations": [], "ok": True}, {"is_error": "no"}, {"exit_code": True},
                    {"observations": {}}, {"output": 3}):
            with self.subTest(rep=rep):
                x = execute(command(), MODEL, {"throttle": Spy(rep)}, FakeRecorder(), EXECUTE)
                self.assertEqual((x.outcome.is_error, x.outcome.exception), (True, "ContractError"))

    def test_without_l0(self):
        x = execute(command(), MODEL, {"throttle": Spy({"observations": [], "exit_code": 0})}, None, EXECUTE,
                    mono=iter([0.0, 7.5]).__next__)
        self.assertEqual((x.outcome.exit_code, x.outcome.elapsed_ms), (0, 7.5))

    def test_targetless_action(self):
        rec = FakeRecorder()
        x = execute(command("escalate", None, {}), MODEL, {"escalate": Spy({})}, rec, EXECUTE)
        self.assertTrue(x.executed)
        self.assertIsNone(rec.events[0][1]["target"])

    def test_args_go_to_recorder_only_after_t17(self):
        rec = FakeRecorderT17()
        execute(command(args={"level": 3}), MODEL, {"throttle": Spy({})}, rec, EXECUTE)
        self.assertEqual(rec.got_args, {"level": 3})
        rec = FakeRecorder()                                         # T17 전: 넘기지 않는다(넘기면 TypeError)
        x = execute(command(args={"level": 3}), MODEL, {"throttle": Spy({})}, rec, EXECUTE)
        self.assertTrue(x.executed)
        self.assertIsNone(x.outcome.exception)

    def test_to_dict_for_the_ledger(self):
        import json
        x = execute(command(), MODEL, {"throttle": Spy(exc=KeyError("secret"))}, FakeRecorder(), EXECUTE)
        d = x.to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)
        self.assertEqual((d["raised"], d["outcome"]["exception"], d["observations"]), ("KeyError", "KeyError", 0))
        self.assertNotIn("secret", json.dumps(d))
        sh = execute(command(), MODEL, {"throttle": Spy({})}).to_dict()
        self.assertEqual((sh["mode"], sh["executed"], sh["outcome"]), (SHADOW, False, None))

    def test_ms_handler_reads_tool_error(self):
        h = ms_handler(lambda t, a: [{"entity": t, "signal": "tool_error", "value": "boom"}])
        rep = h("srv1", {})
        self.assertTrue(rep["is_error"])
        self.assertEqual(len(rep["output"]), len('[{"entity": "srv1", "signal": "tool_error", "value": "boom"}]'))
        self.assertFalse(ms_handler(lambda t, a: [{"signal": "ack"}])("s", {})["is_error"])
        self.assertEqual(ms_handler(lambda t, a: None)("s", {})["observations"], [])


class WithTelemetry(unittest.TestCase):
    """진짜 Telemetry Recorder(T16: action_ref 를 받는다)로 적은 사건이 L0 꼴 검사를 지나는가."""

    def setUp(self):
        self.rec_mod = siblings.load("telemetry", "telemetry", "telemetry.recorder")
        if self.rec_mod is None:
            self.skipTest("Telemetry 를 찾지 못함 -- TELEMETRY_REPO")
        self.ev = siblings.load("telemetry", "telemetry", "telemetry.event")
        self.ledger = siblings.load("telemetry", "telemetry", "telemetry.ledger")

    def recorder(self):
        sink = self.ledger.MemorySink()
        return self.rec_mod.Recorder("run-1", sink, source="inproc:test", hasher=lambda s: "a" * 12), sink

    def test_events_are_l0_and_keyed_by_command(self):
        rec, sink = self.recorder()
        x = execute(command(), MODEL, {"throttle": Spy({"observations": [], "is_error": False, "output": "xy"})},
                    rec, EXECUTE)
        self.assertEqual([e["type"] for e in sink.events], ["action.dispatch", "action.result"])
        for e in sink.events:
            self.assertEqual(self.ev.check(e), [])
            self.assertEqual(e["data"]["action_ref"], x.command_id)
        d, r = sink.events[0]["data"], sink.events[1]["data"]
        self.assertEqual((d["decision_ref"], d["action_type"], d["target"]), ("dec-00112233aabbccdd", "throttle", "#" + "a" * 12))
        self.assertEqual((r["is_error"], r["output_chars"]), (False, 2))
        self.assertEqual(x.outcome.is_error, r["is_error"])
        self.assertIn("exit_code", sink.events[1]["unobserved"])

    def test_exception_path(self):
        rec, sink = self.recorder()
        x = execute(command(), MODEL, {"throttle": Spy(exc=ValueError("m"))}, rec, EXECUTE)
        r = sink.events[1]["data"]
        self.assertEqual((r["exception"], r["is_error"]), ("ValueError", True))
        self.assertEqual((x.outcome.exception, x.outcome.is_error), ("ValueError", True))

    def test_shadow_writes_nothing(self):
        rec, sink = self.recorder()
        execute(command(), MODEL, {"throttle": Spy({})}, rec, SHADOW)
        self.assertEqual(sink.events, [])


if __name__ == "__main__":
    unittest.main()
