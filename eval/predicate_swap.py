"""술어 · 인자 한 벌 바꿔 끼우기(CMD-A4) -- MS · guard · health 의 **복사본**에서 자기 술어 · 인자 모듈을 action 의 한 벌을 다시
내보내는 얇은 모듈로 바꾸고, 그 저장소의 시험 전체를 돌린다. 원본은 건드리지 않는다.

    python3 eval/predicate_swap.py <MS> <guard> <health> <Telemetry> <DC> [<Sensor>]

얇은 모듈이 하는 일이 곧 각 저장소가 import 쪽으로 바꿀 때의 차이다(docs/PREDICATE.md):
    MS      props_of 는 집합으로 감싼다(model.py 가 `|=` 로 쓴다). ToolSpec.check_args 는 action.params.check_args 로
    guard   그대로 다시 내보낸다
    health  check 는 refs=False · named=True 로 부른다(verification-record/1)
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ACTION = pathlib.Path(__file__).resolve().parent.parent

MS_PRED = '''"""(바꿔 끼움) action 의 술어 한 벌."""
from action.predicate import OPS, UNARY, _rhs, all_hold, check, holds
from action.predicate import props_of as _props_of


def props_of(preds) -> set:
    return set(_props_of(preds))
'''
GUARD_PRED = '"""(바꿔 끼움)"""\nfrom action.predicate import OPS, _rhs, check, holds, props_of\n'
GUARD_PARAMS = '"""(바꿔 끼움)"""\nfrom action.params import TYPES, check_args\n'
HEALTH_PRED = '''"""(바꿔 끼움)"""
from action import predicate as _a
from action.predicate import OPS, UNARY, holds


def check(pred):
    return _a.check(pred, refs=False, named=True)
'''
MS_CHECK_OLD = '''    def check_args(self, args) -> list:
        if not isinstance(args, dict):'''
MS_CHECK_NEW = '''    def check_args(self, args) -> list:
        from action.params import check_args
        return check_args(self.params, args)

    def _old_check_args(self, args) -> list:
        if not isinstance(args, dict):'''


def run(name, src, edits, env, siblings):
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        d = root / name
        shutil.copytree(src, d, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        for link, target in siblings.items():           # 옆 저장소(시험들이 ../<이름> 으로 찾는다)
            if link != name and not (root / link).exists():
                os.symlink(pathlib.Path(target).resolve(), root / link)
        for rel, new, old in edits:
            f = d / rel
            if old is None:
                f.write_text(new, encoding="utf-8")
            else:
                s = f.read_text(encoding="utf-8")
                assert s.count(old) == 1, (name, rel)
                f.write_text(s.replace(old, new), encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q"], cwd=d, capture_output=True, text=True,
                           env={**os.environ, **env})
        ran = next((ln for ln in r.stderr.splitlines() if ln.startswith("Ran ")), "?")
        print(f"{name:7s} {ran} · {r.stderr.strip().splitlines()[-1]}")
        if r.returncode:
            print(r.stderr[-3000:])
        return r.returncode == 0


def main(ms, guard, health, telemetry, dc, sensor=None) -> int:
    path = os.pathsep.join([str(ACTION), telemetry] + ([sensor] if sensor else []))
    sib = {"action": ACTION, "Telemetry": telemetry, "telemetry": telemetry, "DC": dc, "dc": dc, "MS": ms, "ms": ms,
           "guard": guard, "health": health, **({"Sensor": sensor} if sensor else {})}
    ok = [
        run("ms", ms, [("ms/predicate.py", MS_PRED, None), ("ms/tools.py", MS_CHECK_NEW, MS_CHECK_OLD)],
            {"PYTHONPATH": path, "MS_ACTION_PATH": str(ACTION), "MS_GUARD_PATH": guard, "MS_DC_PATH": dc,
             "MS_REPO": ms}, sib),
        run("guard", guard, [("guard/predicate.py", GUARD_PRED, None), ("guard/params.py", GUARD_PARAMS, None)],
            {"PYTHONPATH": path, "MS_REPO": ms}, sib),
        run("health", health, [("health/predicate.py", HEALTH_PRED, None)], {"PYTHONPATH": path, "MS_REPO": ms}, sib),
    ]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:7]))
