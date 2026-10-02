"""변이 시험 -- 꼴 코드를 일부러 망가뜨려 시험이 빨개지는지 본다. 하나라도 초록으로 남으면 그 시험은 헛돈다.

    python3 eval/mutation.py            # 복사본에서 변이마다 시험을 돌린다. 원본은 건드리지 않는다
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
F, C, M = "action/forms.py", "action/canonical.py", "action/l0map.py"
SP, EX = "action/spec.py", "action/executor.py"
# (이름, 파일, 바꿀 글, 바꿀 것)
MUTANTS = [
    ("꼴을 연다(모르는 칸 허용)", F, 'errs = [f"모르는 칸 {k!r}" for k in sorted(set(d) - known, key=str)]', "errs = []"),
    ("빠진 칸을 허용", F, 'errs += [f"빠진 칸 {k!r}" for k in sorted(required - set(d))]', "pass"),
    ("id 를 다시 계산하지 않음", F, "if cls.ID and d[cls.ID] != obj.to_dict()[cls.ID]:", "if False:"),
    ("판본을 보지 않음", F, "    if v != want:\n", "    if False:\n"),
    ("used_keys 를 정렬하지 않음", F, "tuple(sorted(self.used_keys))", "tuple(self.used_keys)"),
    ("겹치는 used_keys 허용", F, "elif len(set(self.used_keys)) != len(self.used_keys):", "elif False:"),
    ("해시가 칸 하나(args)를 빠뜨림", F, "for f in fields(self)}", 'for f in fields(self) if f.name != "args"}'),
    ("bool 을 int 로 받음", F, "return isinstance(v, int) and not isinstance(v, bool)", "return isinstance(v, int)"),
    ("못 본 결과를 성공으로 메움", F, 'is_error: "bool | None" = None', 'is_error: "bool | None" = False'),
    ("예외 메시지를 받음", F, r'EXCEPTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")', r'EXCEPTION_NAME = re.compile(r"^.+$")'),
    ("기한이 발행보다 이를 수 있음", F, "elif _is_num(self.issued_at) and self.deadline <= self.issued_at:", "elif False:"),
    ("모르는 author_kind 허용", F, "if self.author_kind not in AUTHOR_KINDS:", "if False:"),
    ("정책 판본 없이 허용", F, r'POLICY_REF = re.compile(r"^[^@\s]+@[^@\s]+$")', r'POLICY_REF = re.compile(r"^\S+$")'),
    ("args 가 JSON 인지 보지 않음", F, '    errs.extend(f"args: {e}" for e in check_json(v, "args"))\n', ""),
    ("열쇠를 정렬하지 않음", C, "(obj, sort_keys=True", "(obj, sort_keys=False"),
    ("ASCII 로 바꿔 씀", C, "ensure_ascii=False, separators", "ensure_ascii=True, separators"),
    ("구분자에 빈칸", C, 'separators=(",", ":")', 'separators=(", ", ": ")'),
    ("JSON 이 아닌 값을 문자열로", C, '    return [f"{path}: JSON 이 아닌 값 {type(v).__name__}"]', "    return []"),
    ("NaN 을 받음", C, 'return [f"{path}: 유한하지 않은 수 {v!r}"]', "return []"),
    ("해시 길이를 줄임", C, "hexdigest()[:16]", "hexdigest()[:12]"),
    ("겨냥 평문을 L0 로", M, 'f"#{hasher(command.target)}"', "command.target"),
    ("L0 로 결정 대신 의도를 잇는다", M, '"decision_ref": command.decision_ref', '"decision_ref": command.intent_id'),
    ("L0 결과의 못 봄을 False 로", M, "{k: getattr(outcome, k) for k in", '{k: (False if k == "is_error" and getattr(outcome, k) is None else getattr(outcome, k)) for k in'),
    ("베낀 L0 칸이 흘러감", M, '"output_chars", "elapsed_ms"),\n}', '"output_chars", "elapsed_ms", "stderr_chars"),\n}'),
    ("빠진 칸 설명을 지움", M, '    "ActionCommand.args": ', '    "_args": '),
    # ── 행동 명세(action/spec.py) ──
    ("모르는 위험 등급을 받음", SP, "        if self.risk not in RISKS:", "        if False:"),
    ("사후조건에 속성 참조를 받음(V4)", SP, "        if not refs:", "        if False:"),
    ("사후조건이 있는데 창 없이 받음", SP, "        if isinstance(self.postcondition, tuple) and self.postcondition and self.window_ms is None:", "        if False:"),
    ("겨냥 없는 행동에 $target 을 받음", SP, '                if c["entity"] == "$target" and self.target_model is None:', "                if False:"),
    ("모르는 연산을 받음", SP, "    if p[1] not in BINARY_OPS:", "    if False:"),
    ("명세 꼴을 연다", SP, '        if bad:\n            raise ContractError("ActionSpec", [f"모르는 칸 {bad}"])', "        pass"),
    ("겹치는 행동 이름을 받음", SP, "        if dup:", "        if False:"),
    ("MS 투영이 사전조건을 버림", SP, '"params": spec.params, "preconditions": _plain(spec.preconditions), "risk": spec.risk}', '"params": spec.params, "preconditions": [], "risk": spec.risk}'),
    ("Health 에 판본 없는 이름을 줌", SP, 'return {"spec": spec.ref,', 'return {"spec": spec.name,'),
    # ── 실행기(action/executor.py) ──
    ("shadow 가 처리기를 부름", EX, "    if mode == SHADOW:\n        return Execution(command.id, mode, False, None, plan)\n", ""),
    ("모형에 없는 행동을 실행", EX, "    if model.get(command.action) is None:", "    if False:"),
    ("L0 를 명령 id 로 잇지 않음", EX, "action_ref=command.id) if recorder", "action_ref=None) if recorder"),
    ("보고 안 한 결과를 성공으로 메움", EX, 'vals = {k: rep[k] for k in ("is_error", "exit_code", "status_code") if rep.get(k) is not None}', 'vals = {"is_error": False, **{k: rep[k] for k in ("is_error", "exit_code", "status_code") if rep.get(k) is not None}}'),
    ("처리기 결과를 검사하지 않음", EX, '            if bad:\n                raise ContractError("handler", bad)', "            pass"),
    ("관측을 버림", EX, 'obs = list(rep.get("observations") or [])', "obs = []"),
    ("MS 의 tool_error 를 못 읽음", EX, 'any(o.get("signal") == "tool_error" for o in obs)', "False"),
]


def run(tree: pathlib.Path) -> bool:
    # -B: 바이트코드를 쓰지 않는다. 같은 초 · 같은 크기의 변이가 낡은 .pyc 를 재사용해 헛 RED 를 내지 않게
    r = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q"], cwd=tree, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    survived = []
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp) / "action"
        shutil.copytree(ROOT, base, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        if not run(base):
            print("원본이 초록이 아니다 -- 변이를 돌리지 않는다")
            return 2
        for name, rel, old, new in MUTANTS:
            path = base / rel
            orig = path.read_text(encoding="utf-8")
            if orig.count(old) != 1:
                print(f"?? {name}: 바꿀 글이 {orig.count(old)} 번 나온다")
                survived.append(name)
                continue
            path.write_text(orig.replace(old, new), encoding="utf-8")
            try:
                green = run(base)
            finally:
                path.write_text(orig, encoding="utf-8")
            print(f"{'SURVIVED' if green else 'RED     '}  {name}")
            if green:
                survived.append(name)
    print(f"\n{len(MUTANTS) - len(survived)}/{len(MUTANTS)} RED")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
