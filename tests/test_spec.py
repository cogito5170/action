import json
import unittest

from action import ContractError
from action.forms import ActionCommand
from action.spec import (BINARY_OPS, RISKS, UNARY_OPS, ActionModel, ActionSpec, to_guard_spec, to_ms_tool,
                         verify_args)
from tests import siblings

THROTTLE = {"name": "throttle", "target_model": "Server", "risk": "local", "description": "CPU 클럭을 낮춘다",
            "params": {"level": {"type": "integer", "min": 1, "max": 3}},
            "preconditions": [["status", "in", ["hot", "critical"]]]}
POST = [{"entity": "$target", "pred": ["status", "in", ["ok", "warm"]]}]


def spec(**kw):
    d = dict(name="throttle", version="1", target_model="Server", params={"level": {"type": "integer", "min": 1}},
             preconditions=(("status", "in", ["hot", "critical"]),), risk="local", postcondition=tuple(POST),
             window_ms=60_000, description="d")
    d.update(kw)
    return ActionSpec(**d)


class Form(unittest.TestCase):
    def test_round_trip_and_digest(self):
        s = spec()
        d = json.loads(json.dumps(s.to_dict()))
        self.assertEqual(ActionSpec.from_dict(d), s)
        self.assertEqual(ActionSpec.from_dict(d).digest(), s.digest())
        self.assertEqual(s.ref, "throttle@1")
        self.assertNotEqual(spec(version="2").digest(), s.digest())

    def test_closed(self):
        d = spec().to_dict()
        d["handler"] = "x"
        with self.assertRaises(ContractError):
            ActionSpec.from_dict(d)
        d = spec().to_dict()
        del d["version"]
        with self.assertRaises(ContractError):
            ActionSpec.from_dict(d)

    def test_bad_values(self):
        bad = [dict(name=""), dict(name="a b"), dict(version=""), dict(version="1@2"), dict(risk="dangerous"),
               dict(target_model=""), dict(params={"x": {"type": "integer", "extra": 1}}), dict(params={"x": {"type": "date"}}),
               dict(preconditions=(("status", "~", 1),)), dict(preconditions=(("status",),)),
               dict(preconditions=(("status", "exists", 1, 2),)), dict(preconditions=(("", "==", 1),)),
               dict(postcondition=({"entity": "$target", "pred": ["s", "==", {"prop": "t"}]},)),   # V4
               dict(postcondition=({"entity": "$who", "pred": ["s", "==", 1]},)),
               dict(postcondition=({"entity": "$target"},)), dict(window_ms=None), dict(window_ms=0),
               dict(window_ms=True), dict(window_ms=float("inf")),
               dict(target_model=None),                       # $target 이 있는데 겨냥 없는 행동
               dict(schema="action-spec/2")]
        for kw in bad:
            with self.subTest(**{k: repr(v) for k, v in kw.items()}), self.assertRaises(ContractError):
                spec(**kw)

    def test_allowed(self):
        spec(target_model=None, postcondition=({"entity": "$run.agent", "pred": ["execution_health", "==", "X"]},))
        spec(postcondition=(), window_ms=None)
        spec(preconditions=(("load", "<", {"prop": "cap", "mul": 0.9}), ("fan", "exists")))   # 사전조건은 속성 참조 허용
        spec(postcondition=({"entity": "tool:r1:WebFetch", "pred": ["x", "missing"]},))

    def test_ops_are_the_ms_set(self):
        self.assertEqual(len(BINARY_OPS) + len(UNARY_OPS), 10)
        self.assertEqual(RISKS, ("read", "local", "external", "irreversible"))


class Frozen(unittest.TestCase):
    """action-spec/1 · action-model/1 동결(BD-108, CMD-A4). 바꿀 때는 판본을 올려 더하는 쪽으로만."""
    GOLDEN = {"spec": "4c144c894aa97e67", "model": "d4a09c3c79212ec6"}

    def test_golden(self):
        self.assertEqual(spec().digest(), self.GOLDEN["spec"])
        self.assertEqual(ActionModel("m1", (spec(name="b"), spec(name="a"))).digest(), self.GOLDEN["model"])

    def test_fields_are_fixed(self):
        self.assertEqual(sorted(spec().to_dict()), sorted(["schema", "name", "version", "target_model", "params",
                                                           "preconditions", "risk", "postcondition", "window_ms",
                                                           "description"]))
        self.assertEqual(spec().to_dict()["schema"], "action-spec/1")
        self.assertEqual(ActionModel("m1", ()).to_dict()["schema"], "action-model/1")

    def test_params_follow_ms(self):
        spec(params={"x": {"min": 0}})                          # type 이 없으면 number(MS PropertySpec 과 같다)
        spec(params={"b": {"type": "bool", "required": False}})
        for bad in ({"b": {"type": "boolean"}}, {"e": {"type": "enum"}}, {"x": {"min": "0"}}):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                spec(params=bad)
        with self.assertRaises(ContractError):
            spec(preconditions=(("status", "in", "hot"),))     # in 의 값은 목록(MS check 와 같다)


class Model(unittest.TestCase):
    def test_sorted_and_unique(self):
        m = ActionModel("m1", (spec(name="b"), spec(name="a")))
        self.assertEqual(m.names(), ("a", "b"))
        self.assertEqual(ActionModel.from_dict(json.loads(json.dumps(m.to_dict()))), m)
        with self.assertRaises(ContractError):
            ActionModel("m1", (spec(), spec()))
        self.assertIsNone(m.get("c"))


class Projections(unittest.TestCase):
    """한 집 → 셋의 투영. 옆 저장소가 있으면 그 꼴이 그대로 받는지 본다."""

    def test_verify_args_shape(self):
        a = verify_args(spec())
        self.assertEqual(a, {"spec": "throttle@1", "window_ms": 60_000,
                             "postcondition": [{"entity": "$target", "pred": ["status", "in", ["ok", "warm"]]}]})

    def test_ms_tool_round_trip(self):
        s = ActionSpec.from_tool({**THROTTLE, "effect": [{"signal": "ack"}]}, "1")
        self.assertEqual(to_ms_tool(s), THROTTLE)

    def test_ms_datacenter_tools(self):
        root = siblings.repo("ms", "ms")
        if root is None:
            self.skipTest("MS 를 찾지 못함 -- MS_REPO")
        tools = json.loads((root / "ms" / "examples" / "datacenter.json").read_text(encoding="utf-8"))["tools"]
        ToolSpec = siblings.load("ms", "ms", "ms.tools").ToolSpec
        for t in tools:
            with self.subTest(t["name"]):
                s = ActionSpec.from_tool(t, "1")
                want = {k: v for k, v in t.items() if k != "effect"}
                self.assertEqual({k: v for k, v in to_ms_tool(s).items() if k in want or v}, want)
                a, b = ToolSpec.from_dict(t), ToolSpec.from_dict(to_ms_tool(s))
                self.assertEqual(a.card(), b.card())
                self.assertEqual(a.preconditions, b.preconditions)

    def test_ms_predicate_ops(self):
        pred = siblings.load("ms", "ms", "ms.predicate")
        if pred is None:
            self.skipTest("MS 를 찾지 못함")
        self.assertEqual(set(pred.OPS), set(BINARY_OPS))

    def test_guard_spec(self):
        g = siblings.load("guard", "guard")
        if g is None:
            self.skipTest("guard 를 찾지 못함 -- GUARD_REPO")
        s = ActionSpec.from_tool(THROTTLE, "1")
        self.assertEqual(g.ActionSpec(**to_guard_spec(s)),
                         g.ActionSpec("throttle", "Server", {"level": {"type": "integer", "min": 1, "max": 3}},
                                      (("status", "in", ["hot", "critical"]),), "local"))
        m = g.GuardModel.from_dict({"specs": [to_guard_spec(spec(name=n)) for n in ("a", "b")]})
        self.assertEqual(set(m.specs), {"a", "b"})

    def test_health_verify(self):
        v = siblings.load("health", "health", "health.verification")
        if v is None:
            self.skipTest("health 를 찾지 못함 -- HEALTH_REPO")
        s = spec(postcondition=({"entity": "$target", "pred": ["status", "==", "ok"]},), window_ms=10_000)
        cmd = ActionCommand(intent_id="int-" + "0" * 16, decision_ref="dec-x", action="throttle", target="srv1",
                            args={"level": 1}, issued_at=1_000.0, deadline=None)
        read = {"value": "ok", "status": "OBSERVED", "freshness": "FRESH", "observed_at": 2_000.0, "time_base": "unix_ms"}
        r = v.verify(cmd, run="r1", subjects={"scope": "r1"}, reads={("srv1", "status"): read}, evaluated_at=3_000.0,
                     **verify_args(s))
        self.assertEqual((r.result, r.reason, r.spec), ("VERIFIED", "MET", "throttle@1"))
        early = dict(read, observed_at=500.0)              # 명령 전 관측은 근거가 아니다
        r = v.verify(cmd, run="r1", subjects={"scope": "r1"}, reads={("srv1", "status"): early}, evaluated_at=20_000.0,
                     **verify_args(s))
        self.assertEqual(r.result, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
