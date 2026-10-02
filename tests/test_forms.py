import json
import math
import unittest

from action import ActionCommand, ActionIntent, ActionOutcome, ContractError, canonical_json, digest
from action.forms import COMMAND_SCHEMA, INTENT_SCHEMA, OUTCOME_SCHEMA


def intent(**kw):
    d = dict(dc_id="dc-0123456789abcdef", policy="execution_control@dc-builder-3", action="RETRY", target="svc:db",
             args={"level": 2, "note": "한글"}, rationale="retry_budget 남음", used_keys=["execution.health", "budget.retry"],
             author_kind="rule")
    d.update(kw)
    return ActionIntent(**d)


def command(**kw):
    d = dict(intent_id=intent().id, decision_ref="dec-00112233aabbccdd", action="RETRY", target="svc:db",
             args={"level": 2}, issued_at=1759363200000.0, deadline=1759363260000.0)
    d.update(kw)
    return ActionCommand(**d)


def outcome(**kw):
    d = dict(command_id=command().id, is_error=False, exit_code=0, status_code=None, exception=None, output_chars=12,
             elapsed_ms=41.5)
    d.update(kw)
    return ActionOutcome(**d)


MAKERS = {"ActionIntent": (ActionIntent, intent), "ActionCommand": (ActionCommand, command),
          "ActionOutcome": (ActionOutcome, outcome)}

# 꼴 · 정준 JSON · 해시가 바뀌면 이 값이 바뀐다. 바꿀 때는 판본(schema)도 올린다
GOLDEN = {"ActionIntent": "int-38333d4550b3662b", "ActionCommand": "cmd-868c316d2acfac69",
          "ActionOutcome": "86ef031184be74ee"}


class RoundTrip(unittest.TestCase):
    def test_object_dict_json_object(self):
        for name, (cls, make) in MAKERS.items():
            with self.subTest(name):
                o = make()
                d = o.to_dict()
                s = canonical_json(d)
                back = cls.from_dict(json.loads(s))
                self.assertEqual(back, o)
                self.assertEqual(canonical_json(back.to_dict()), s)

    def test_schema_field_is_versioned(self):
        self.assertEqual(intent().to_dict()["schema"], INTENT_SCHEMA)
        self.assertEqual(command().to_dict()["schema"], COMMAND_SCHEMA)
        self.assertEqual(outcome().to_dict()["schema"], OUTCOME_SCHEMA)

    def test_unobserved_results_stay_none(self):
        o = ActionOutcome(command_id=command().id)
        d = o.to_dict()
        for k in ("is_error", "exit_code", "status_code", "exception", "output_chars", "elapsed_ms"):
            self.assertIsNone(d[k], k)            # 기본값으로 메우지 않는다 -- 결과 없음은 성공이 아니다
        self.assertEqual(ActionOutcome.from_dict(json.loads(canonical_json(d))), o)

    def test_canonical_json_is_one_byte_string(self):
        s = canonical_json(intent().to_dict())
        self.assertNotIn(" ", s.replace("retry_budget 남음", ""))
        self.assertIn("한글", s)                  # ensure_ascii=False
        keys = list(json.loads(s))
        self.assertEqual(keys, sorted(keys))


class Closed(unittest.TestCase):
    def test_unknown_field_rejected(self):
        for name, (cls, make) in MAKERS.items():
            with self.subTest(name):
                d = make().to_dict()
                d["extra"] = 1
                with self.assertRaises(ContractError) as cm:
                    cls.from_dict(d)
                self.assertIn("모르는 칸 'extra'", str(cm.exception))

    def test_missing_field_rejected(self):
        for name, (cls, make) in MAKERS.items():
            for k in make().to_dict():
                with self.subTest(name, field=k):
                    d = make().to_dict()
                    del d[k]
                    with self.assertRaises(ContractError):
                        cls.from_dict(d)

    def test_unknown_constructor_kw_rejected(self):
        with self.assertRaises(TypeError):
            intent(severity="high")

    def test_other_schema_version_rejected(self):
        for name, (cls, make) in MAKERS.items():
            with self.subTest(name):
                d = make().to_dict()
                d["schema"] = d["schema"][:-1] + "2"
                with self.assertRaises(ContractError):
                    cls.from_dict(d)

    def test_tampered_id_rejected(self):
        for name in ("ActionIntent", "ActionCommand"):
            cls, make = MAKERS[name]
            d = make().to_dict()
            d["rationale" if name == "ActionIntent" else "action"] = "STOP"
            with self.subTest(name), self.assertRaises(ContractError) as cm:
                cls.from_dict(d)
            self.assertIn("내용과 맞지 않는다", str(cm.exception))

    def test_bad_values_rejected(self):
        bad = [
            (intent, dict(dc_id="")), (intent, dict(policy="execution_control")), (intent, dict(policy="a@b@c")),
            (intent, dict(action=" ")), (intent, dict(target="")), (intent, dict(args=[1])),
            (intent, dict(args={"x": float("nan")})), (intent, dict(args={"x": {1, 2}})), (intent, dict(args={1: "a"})),
            (intent, dict(used_keys=["a", "a"])), (intent, dict(used_keys=["a", ""])), (intent, dict(used_keys="ab")),
            (intent, dict(author_kind="model")), (intent, dict(rationale=None)),
            (command, dict(intent_id="int-xyz")), (command, dict(decision_ref="")), (command, dict(issued_at=-1)),
            (command, dict(issued_at=True)), (command, dict(issued_at=math.inf)),
            (command, dict(deadline=1759363200000.0)), (command, dict(deadline="soon")),
            (outcome, dict(command_id="cmd-1")), (outcome, dict(is_error=0)), (outcome, dict(exit_code=True)),
            (outcome, dict(exit_code=1.0)), (outcome, dict(exception="ValueError: boom")),
            (outcome, dict(output_chars=-1)), (outcome, dict(elapsed_ms=float("nan"))),
            (outcome, dict(schema="action-outcome/0")),
        ]
        for make, kw in bad:
            with self.subTest(make.__name__, **{k: repr(v) for k, v in kw.items()}):
                with self.assertRaises(ContractError):
                    make(**kw)

    def test_allowed_edge_values(self):
        intent(target=None, args={}, rationale="", used_keys=[])
        command(target=None, deadline=None, issued_at=0)
        outcome(is_error=True, exit_code=137, exception="TimeoutError")
        outcome(output_chars=0, elapsed_ms=0)   # 0 은 못 봄이 아니다


class Hash(unittest.TestCase):
    def test_golden(self):
        self.assertEqual(intent().id, GOLDEN["ActionIntent"])
        self.assertEqual(command().id, GOLDEN["ActionCommand"])
        self.assertEqual(outcome().digest(), GOLDEN["ActionOutcome"])

    def test_same_content_same_id(self):
        a = intent(args={"b": 1, "a": [1, 2]}, used_keys=["y", "x"])
        b = intent(args={"a": [1, 2], "b": 1}, used_keys=["x", "y"])
        self.assertEqual(a.id, b.id)
        self.assertEqual(a, b)

    def test_any_field_changes_id(self):
        base = intent()
        for kw in (dict(dc_id="dc-other"), dict(policy="execution_control@dc-builder-4"), dict(action="STOP"),
                   dict(target=None), dict(args={"level": 3}), dict(rationale="x"), dict(used_keys=["a"]),
                   dict(author_kind="llm")):
            with self.subTest(**{k: repr(v) for k, v in kw.items()}):
                self.assertNotEqual(intent(**kw).id, base.id)
        for kw in (dict(intent_id="int-" + "0" * 16), dict(decision_ref="dec-x"), dict(action="STOP"),
                   dict(target="svc:other"), dict(args={}), dict(issued_at=1), dict(deadline=None)):
            with self.subTest(**{k: repr(v) for k, v in kw.items()}):
                self.assertNotEqual(command(**kw).id, command().id)
        self.assertNotEqual(outcome(exit_code=1).digest(), outcome().digest())

    def test_list_order_in_args_matters(self):
        self.assertNotEqual(intent(args={"a": [1, 2]}).id, intent(args={"a": [2, 1]}).id)

    def test_int_and_float_are_distinct(self):
        # JSON 에서 1 과 1.0 은 다른 글이다 -- 해시가 다른 것이 맞다. 보내는 쪽이 꼴을 고정해야 한다
        self.assertNotEqual(command(issued_at=1).id, command(issued_at=1.0).id)

    def test_digest_matches_canonical_sha256(self):
        import hashlib
        body = intent().body()
        self.assertEqual(digest(body), hashlib.sha256(canonical_json(body).encode()).hexdigest()[:16])
        self.assertEqual(intent().id, "int-" + digest(body))


if __name__ == "__main__":
    unittest.main()
