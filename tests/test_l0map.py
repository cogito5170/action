import dataclasses
import os
import pathlib
import sys
import unittest

from action import ActionCommand, ActionIntent, ActionOutcome, l0map
from tests.test_forms import command, outcome


def _telemetry_catalog():
    """옆 저장소의 Telemetry catalog. 설치돼 있거나, TELEMETRY_REPO · 옆 디렉터리에서 찾는다. 없으면 None."""
    try:
        from telemetry import catalog
        return catalog
    except ImportError:
        pass
    here = pathlib.Path(__file__).resolve().parent.parent
    for p in filter(None, [os.environ.get("TELEMETRY_REPO"), here.parent / "Telemetry", here.parent / "telemetry",
                           here.parent / "cogito5170" / "telemetry"]):
        if (pathlib.Path(p) / "telemetry" / "catalog.py").exists():
            sys.path.insert(0, str(p))
            try:
                from telemetry import catalog
                return catalog
            finally:
                sys.path.remove(str(p))
    return None


def _fields(cls):
    return {f"{cls.__name__}.{f.name}" for f in dataclasses.fields(cls)} | (
        {f"{cls.__name__}.{cls.ID}"} if cls.ID else set())


class Table(unittest.TestCase):
    def test_every_l0_field_has_a_source(self):
        self.assertEqual(tuple(l0map.DISPATCH), l0map.L0_FIELDS["action.dispatch"])
        self.assertEqual(tuple(l0map.RESULT), l0map.L0_FIELDS["action.result"])

    def test_sources_are_real_fields(self):
        known = _fields(ActionCommand) | _fields(ActionOutcome)
        for ev, table in (("dispatch", l0map.DISPATCH), ("result", l0map.RESULT)):
            for k, (src, how) in table.items():
                with self.subTest(ev, field=k):
                    self.assertIn(src, known)
                    self.assertIn(how, ("copy", "hash", "actual"))

    def test_every_form_field_is_mapped_or_explained(self):
        used = {src for t in (l0map.DISPATCH, l0map.RESULT) for src, _ in t.values()}
        for cls in (ActionCommand, ActionOutcome):
            for f in sorted(_fields(cls)):
                with self.subTest(f):
                    self.assertTrue(f in used or f in l0map.NOT_IN_L0, f"{f} 가 대응표에도 NOT_IN_L0 에도 없다")
        self.assertIn("ActionIntent.*", l0map.NOT_IN_L0)

    def test_outcome_is_exactly_l0_result(self):
        own = {f.name for f in dataclasses.fields(ActionOutcome)} - {"schema", "command_id"}
        self.assertEqual(own, set(l0map.L0_FIELDS["action.result"]) - {"action_ref"})


class Build(unittest.TestCase):
    def test_dispatch_data(self):
        c = command()
        d = l0map.dispatch_data(c, c.action, lambda s: "h" * 12)
        self.assertEqual(d, {"action_ref": c.id, "decision_ref": "dec-00112233aabbccdd", "action_type": "RETRY",
                             "target": "#hhhhhhhhhhhh"})
        self.assertNotIn("svc:db", str(d))       # 겨냥 평문이 L0 로 가지 않는다
        self.assertIsNone(l0map.dispatch_data(command(target=None), "STOP", lambda s: "x")["target"])

    def test_result_data_keeps_none(self):
        o = ActionOutcome(command_id=command().id, exit_code=0)
        d = l0map.result_data(o)
        self.assertEqual(set(d), set(l0map.L0_FIELDS["action.result"]))
        self.assertEqual(d["exit_code"], 0)
        self.assertIsNone(d["is_error"])         # 못 본 것을 False 로 메우지 않는다
        self.assertEqual(l0map.result_data(outcome())["elapsed_ms"], 41.5)


class AgainstTelemetry(unittest.TestCase):
    """베낀 L0 칸이 Telemetry 의 지금 catalog 와 같은가. Telemetry 가 옆에 없으면 건너뛴다(까닭을 남긴다)."""

    def test_pinned_copy_matches_catalog(self):
        cat = _telemetry_catalog()
        if cat is None:
            self.skipTest("Telemetry 를 찾지 못함 -- TELEMETRY_REPO 를 주면 대조한다")
        for ev, pinned in l0map.L0_FIELDS.items():
            with self.subTest(ev):
                self.assertEqual(tuple(cat.EVENTS[ev]), pinned)

    def test_built_events_pass_l0_check(self):
        cat = _telemetry_catalog()
        if cat is None:
            self.skipTest("Telemetry 를 찾지 못함")
        import importlib
        event = importlib.import_module(cat.__name__.rsplit(".", 1)[0] + ".event")
        c, o = command(), outcome()
        ev1 = event.make("action.dispatch", "run-1", 0, "action", **l0map.dispatch_data(c, c.action, lambda s: "a" * 12))
        ev2 = event.make("action.result", "run-1", 1, "action", **l0map.result_data(ActionOutcome(command_id=c.id)))
        self.assertEqual(event.check(ev1), [])
        self.assertEqual(sorted(ev2["unobserved"]), sorted(set(l0map.L0_FIELDS["action.result"]) - {"action_ref"}))
        self.assertEqual(event.check(event.make("action.result", "run-1", 2, "action", **l0map.result_data(o))), [])


if __name__ == "__main__":
    unittest.main()
