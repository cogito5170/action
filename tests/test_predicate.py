"""술어 · 인자 검사 한 벌(CMD-A4) -- 자체 진리표 + MS · guard · health 의 벌과 같은 뜻인지 대조."""
import importlib.util
import itertools
import pathlib
import types
import unittest

from action import params as A
from action import predicate as P
from tests import siblings

VALUES = [{"t": 80, "s": "hot", "f": None, "b": True, "n": 1.0, "budget": 100, "used": 95, "flag": False},
          {"t": "x", "s": None, "budget": True, "used": 85}, {}]
PREDS = [
    ["t", ">", 70], ["t", "<", 70], ["t", "==", 80], ["t", "!=", 81], ["t", ">=", 80], ["t", "<=", 79],
    ["s", "in", ["hot", "critical"]], ["s", "not_in", ["normal"]], ["s", "not_in", ["hot"]],
    ["x", "==", None], ["x", "!=", 1], ["s", "<", 3], ["n", "==", 1], ["b", "==", True], ["flag", "==", False],
    ["x", "missing"], ["x", "exists"], ["t", "exists"], ["f", "missing"], ["f", "exists"],
    ["used", ">=", {"prop": "budget", "mul": 0.9}], ["used", ">=", {"prop": "budget"}], ["used", "<", {"prop": "nope"}],
    ["t", "in", ["a", 80]], ["s", "==", "hot"],
]
BAD = [["t"], ["t", "~", 1], ["t", "in", 3], ["t", "eq"], ["t", "exists", 1], ["t", "in", {"prop": "x"}],
       ["t", ">", {"prop": 3}], ["t", ">", {"prop": "x", "add": 1}], "t == 1", None, ["t", ">", 1, 2]]
ODD_NAMES = [["", "==", 1], [1, "==", 1], [None, "exists"]]     # MS · guard 는 받고 health 는 거절한다


def _load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sibling_file(repo, package, rel):
    root = siblings.repo(repo, package)
    return None if root is None else root / rel


class Own(unittest.TestCase):
    def test_truth(self):
        v = VALUES[0]
        want = [True, False, True, True, True, False, True, True, False, False, False, False, True, True, True,
                True, False, True, True, False, True, False, False, True, True]
        self.assertEqual([P.holds(p, v) for p in PREDS], want)
        self.assertTrue(all(not P.holds(p, {}) for p in PREDS if p[1] != "missing"))
        for ref in ({"prop": "nope"}, {"prop": "budget"}):              # 걸린 속성이 없거나 수가 아니면 != 도 거짓
            self.assertFalse(P.holds(["used", "!=", ref], {"used": 95, "budget": True}), ref)

    def test_check_modes(self):
        for p in PREDS:
            self.assertEqual(P.check(p), [], p)
        for p in BAD:
            self.assertNotEqual(P.check(p), [], p)
        ref = ["used", ">=", {"prop": "budget"}]
        self.assertEqual(P.check(ref), [])
        self.assertNotEqual(P.check(ref, refs=False), [])
        for p in ODD_NAMES:
            self.assertEqual(P.check(p), [], p)                    # MS 와 같다
            self.assertNotEqual(P.check(p, named=True), [], p)     # health 의 자리

    def test_props_of_is_ordered(self):
        self.assertEqual(P.props_of([["used", ">=", {"prop": "budget"}], ["s", "==", 1], ["used", "<", 3]]),
                         ["used", "budget", "s"])
        self.assertTrue(P.all_hold([["t", ">", 1], ["s", "exists"]], VALUES[0]))
        self.assertFalse(P.all_hold([["t", ">", 1], ["x", "exists"]], VALUES[0]))


class SameAsMS(unittest.TestCase):
    def setUp(self):
        f = _sibling_file("ms", "ms", "ms/predicate.py")
        if f is None:
            self.skipTest("MS 를 찾지 못함 -- MS_REPO")
        self.ms = _load_file(f, "_ms_predicate")

    def test_holds_and_check(self):
        self.assertEqual(set(self.ms.OPS), set(P.OPS))
        for p, v in itertools.product(PREDS, VALUES):
            self.assertEqual(P.holds(p, v), self.ms.holds(p, v), (p, v))
        for p in PREDS + BAD + ODD_NAMES:
            self.assertEqual(P.check(p), self.ms.check(p), p)       # 글까지 같다
        for ps in ([PREDS[0], PREDS[20]], PREDS):
            self.assertEqual(set(P.props_of(ps)), self.ms.props_of(ps))
            for v in VALUES:
                self.assertEqual(P.all_hold(ps, v), self.ms.all_hold(ps, v))


class SameAsGuard(unittest.TestCase):
    def setUp(self):
        self.g = siblings.load("guard", "guard", "guard.predicate")
        if self.g is None:
            self.skipTest("guard 를 찾지 못함 -- GUARD_REPO")

    def test_holds_check_props(self):
        for p, v in itertools.product(PREDS, VALUES):
            self.assertEqual(P.holds(p, v), self.g.holds(p, v), (p, v))
        for p in PREDS + BAD + ODD_NAMES:
            self.assertEqual(P.check(p) == [], self.g.check(p) == [], p)
        self.assertEqual(P.props_of(PREDS), self.g.props_of(PREDS))

    def test_guards_own_predicate_tests_pass_on_this_copy(self):
        f = _sibling_file("guard", "guard", "tests/test_predicate.py")
        src = f.read_text(encoding="utf-8").replace("from guard import predicate as P", "from action import predicate as P")
        self.assertIn("from action import predicate as P", src)
        _run_tests(self, src, "_guard_test_predicate")


class SameAsHealth(unittest.TestCase):
    def setUp(self):
        self.h = siblings.load("health", "health", "health.predicate")
        if self.h is None:
            self.skipTest("health 를 찾지 못함 -- HEALTH_REPO")

    def test_holds_and_check_in_postcondition_mode(self):
        for p, v in itertools.product([p for p in PREDS if not isinstance(p[-1], dict)], VALUES):
            self.assertEqual(P.holds(p, v), self.h.holds(p, v), (p, v))
        for p in PREDS + BAD + ODD_NAMES:
            self.assertEqual(P.check(p, refs=False, named=True) == [], self.h.check(p) == [], p)

    def test_healths_own_predicate_tests_pass_on_this_copy(self):
        f = _sibling_file("health", "health", "tests/test_predicate.py")
        shim = "import types as _t\nfrom action import predicate as _a\n" \
               "predicate = _t.SimpleNamespace(OPS=_a.OPS, holds=_a.holds, check=lambda p: _a.check(p, refs=False, named=True))\n"
        src = f.read_text(encoding="utf-8").replace("from health import predicate\n", shim)
        self.assertIn("_a.check(p, refs=False, named=True)", src)
        _run_tests(self, src, "_health_test_predicate")


def _run_tests(case, src, name):
    mod = types.ModuleType(name)
    mod.__file__ = str(pathlib.Path(__file__))
    exec(compile(src, name, "exec"), mod.__dict__)
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    result = unittest.TestResult()
    suite.run(result)
    case.assertEqual((result.failures, result.errors), ([], []))
    case.assertGreater(result.testsRun, 0)


# ── 인자 검사 ────────────────────────────────────────────────────────────────

PARAMS = [{}, {"level": {"type": "integer", "min": 1, "max": 3}}, {"note": {"type": "string"}},
          {"x": {"min": 0.5, "unit": "s"}}, {"b": {"type": "bool", "required": False}},
          {"e": {"type": "enum", "values": ["a", "b"]}}, {"level": {"type": "integer"}, "note": {"type": "string", "required": False}}]
ARGS = [{}, {"level": 2}, {"level": 2.0}, {"level": 2.5}, {"level": 0}, {"level": 4}, {"level": True}, {"level": "2"},
        {"note": "n"}, {"note": 3}, {"x": 0.4}, {"x": 1}, {"x": float("nan")}, {"x": True}, {"b": False}, {"b": 0},
        {"e": "a"}, {"e": "c"}, {"zzz": 1}, {"level": 1, "note": "n"}, [1], None]


class Params(unittest.TestCase):
    def test_own(self):
        self.assertEqual(A.check_args(PARAMS[1], {"level": 2}), [])
        self.assertEqual(A.check_args(PARAMS[1], {"level": 2.0}), [])          # 정수 자리의 2.0 은 2
        self.assertEqual(A.check_args(PARAMS[1], {"level": True}), ["level: 정수가 아니다 (True)"])
        self.assertEqual(A.check_args(PARAMS[1], {}), ["인자 level 가 없다"])
        self.assertEqual(A.check_args({"y": {"type": "date"}}, {"y": 1}), ["y: 모르는 타입 'date'"])
        self.assertEqual(A.coerce("level", {"type": "integer"}, 2.0), (2, None))
        self.assertEqual(A.check_args({"x": {}}, {"x": True}), ["x: 수가 아니다 (True)"])       # type 없음 = number
        self.assertEqual(A.check_args(PARAMS[1], {"level": 4}), ["level: 4 > 최대 3"])
        self.assertEqual(A.check_args(PARAMS[1], {"level": 0}), ["level: 0 < 최소 1"])
        self.assertEqual(A.check_args(PARAMS[1], {"level": 2, "zzz": 1}), ["모르는 인자 zzz"])
        self.assertEqual(A.check_args(PARAMS[4], {}), [])                                        # required: False
        self.assertEqual(A.check_args(PARAMS[5], {"e": "c"}), ["e: 'c' 는 ['a', 'b'] 밖이다"])
        self.assertEqual(A.check_args(PARAMS[1], [1]), ["args 가 객체가 아니다"])

    def test_spec_errors(self):
        for ps in PARAMS:
            self.assertEqual(A.spec_errors(ps), [], ps)
        for bad in ([], {"x": 1}, {"x": {"type": "date"}}, {"x": {"kind": "integer"}}, {"x": {"type": "enum"}},
                    {"x": {"min": "1"}}, {"x": {"required": "yes"}}, {"": {}}):
            self.assertNotEqual(A.spec_errors(bad), [], bad)

    def test_same_as_ms(self):
        tools = siblings.load("ms", "ms", "ms.tools")
        if tools is None:
            self.skipTest("MS 를 찾지 못함 -- MS_REPO")
        for ps, a in itertools.product(PARAMS, ARGS):
            ms = tools.ToolSpec("t", "*", params=ps).check_args(a)
            self.assertEqual(A.check_args(ps, a), ms, (ps, a))        # 글까지 같다

    def test_same_as_guard(self):
        g = siblings.load("guard", "guard", "guard.params")
        if g is None:
            self.skipTest("guard 를 찾지 못함 -- GUARD_REPO")
        for ps, a in itertools.product(PARAMS + [{"y": {"type": "date"}}], ARGS):
            self.assertEqual(A.check_args(ps, a), g.check_args(ps, a), (ps, a))


if __name__ == "__main__":
    unittest.main()
