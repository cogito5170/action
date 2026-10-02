"""PC-19 탐침(CMD-A2) -- MS 를 ActionIntent 로 옮길 때 무엇이 깨지나를 **복사본에서** 잰다. MS 원본은 건드리지 않는다.

    python3 eval/pc19_probe.py <MS 저장소> <Telemetry 저장소> <DC 저장소>

탐침마다 MS 를 임시 디렉터리에 복사하고, 옮김의 한 요소를 넣고, MS 시험 전체를 돌려 빨개진 시험을 적는다.
P0 은 깨짐을 재지 않는다. D1(ActionCommand.decision_ref)의 전제를 잰다: 도구 실행 **직전**에 지은 DecisionRecord id 가
실행 뒤에 지은 id 와 같은가(다르면 그 시험이 AssertionError 로 빨개진다). 같으면 순서만 바꾸면 된다.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

PIPE, RT, LLM, L0 = "ms/pipeline.py", "ms/runtime.py", "ms/llm.py", "ms/l0.py"
PROBES = {
    "P0 DecisionRecord id 를 실행 직전에 지어도 같은가(D1)": [
        (PIPE, "            tool = self.reg.get(p.tool)                 # 여기",
         "            if getattr(self, 'before_execute', None):\n                self.before_execute(res)\n"
         "            tool = self.reg.get(p.tool)                 # 여기"),
        (RT, '        res = pipe.run(request["task"]',
         "        _pre = []\n        pipe.before_execute = lambda r: _pre.append(self._record(request, sid, state, cplan, pplan, "
         "choice, provider, r, 0.0, run_id, source)[0].id)\n"
         '        res = pipe.run(request["task"]'),
        (RT, "        dec, rec = self._record(request, sid, state, cplan, pplan, choice, provider, res, total_ms, run_id, source)\n",
         "        dec, rec = self._record(request, sid, state, cplan, pplan, choice, provider, res, total_ms, run_id, source)\n"
         "        if _pre:\n            assert _pre == [dec.id], (_pre, dec.id)\n"
         "            with open(__import__('os').environ['PC19_PRE_LOG'], 'a') as _f:\n                _f.write(dec.id + '\\n')\n"),
    ],
    "P1 제안 기록의 칸 이름을 ActionIntent 로(tool→action)": [
        (LLM, 'return {"tool": self.tool, "target"', 'return {"action": self.tool, "target"'),
    ],
    "P2 실행의 L0 사건을 tool.* → action.*": [
        (PIPE, 'with self.rec.tool(tool.name, {"target": p.target, "args": p.args}, call_index=len(res.calls) - 1) as t:',
         "with self.rec.action(tool.name, target=p.target) as t:"),
        (L0, "    @contextmanager\n    def tool(self, *a, **kw):\n        yield _Nothing()",
         "    @contextmanager\n    def tool(self, *a, **kw):\n        yield _Nothing()\n\n"
         "    @contextmanager\n    def action(self, *a, **kw):\n        yield _Nothing()"),
    ],
    "P3 A8 되풀이 열쇠에 rationale 을 넣음(intent_id 를 열쇠로 쓴 것과 같다)": [
        (LLM, "return json.dumps([self.tool, self.target, self.args], sort_keys=True",
         "return json.dumps([self.tool, self.target, self.args, self.rationale], sort_keys=True"),
    ],
    "P4 rationale 을 500 자에서 자르지 않음": [
        (LLM, 'str(obj.get("rationale", ""))[:500]', 'str(obj.get("rationale", ""))'),
    ],
}


def main(ms, telemetry, dc) -> int:
    for name, edits in PROBES.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            d = root / "ms"
            shutil.copytree(ms, d, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            os.symlink(pathlib.Path(telemetry).resolve(), root / "Telemetry")     # MS 시험은 ../Telemetry 를 찾는다
            for rel, old, new in edits:
                f = d / rel
                s = f.read_text(encoding="utf-8")
                if s.count(old) != 1:
                    print(f"\n## {name}: 바꿀 글이 {s.count(old)} 번 -- MS 가 바뀌었다")
                    break
                f.write_text(s.replace(old, new), encoding="utf-8")
            else:
                log = root / "pre.log"
                r = subprocess.run([sys.executable, "-m", "unittest", "-v"], cwd=d, capture_output=True, text=True,
                                   env={**os.environ, "MS_DC_PATH": str(pathlib.Path(dc).resolve()),
                                        "PC19_PRE_LOG": str(log)})
                bad = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+) \((\S+)\)", r.stderr, re.M)))
                print(f"\n## {name}: {r.stderr.strip().splitlines()[-1]}")
                if log.exists():
                    ids = log.read_text().split()
                    print(f"  실행 직전 id == 실행 뒤 id: 실행 {len(ids)} 번 · 결정 {len(set(ids))} 개")
                for test, cls in bad:
                    print(f"  - {cls.rsplit('.', 1)[0]}.{test}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
