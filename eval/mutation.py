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
SP, EX, PR, PA = "action/spec.py", "action/executor.py", "action/predicate.py", "action/params.py"
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
    ("사후조건에 속성 참조를 받음(V4)", SP, 'e += _pred_errors(c["pred"], f"postcondition[{i}].pred", refs=False)', 'e += _pred_errors(c["pred"], f"postcondition[{i}].pred", refs=True)'),
    ("사후조건이 있는데 창 없이 받음", SP, "        if isinstance(self.postcondition, tuple) and self.postcondition and self.window_ms is None:", "        if False:"),
    ("겨냥 없는 행동에 $target 을 받음", SP, '                if c["entity"] == "$target" and self.target_model is None:', "                if False:"),
    ("모르는 연산을 받음", PR, "    if pred[1] not in OPS:", "    if False:"),
    ("명세 꼴을 연다", SP, '        if bad:\n            raise ContractError("ActionSpec", [f"모르는 칸 {bad}"])', "        pass"),
    ("겹치는 행동 이름을 받음", SP, "        if dup:", "        if False:"),
    ("MS 투영이 사전조건을 버림", SP, '"params": spec.params, "preconditions": _plain(spec.preconditions), "risk": spec.risk}', '"params": spec.params, "preconditions": [], "risk": spec.risk}'),
    ("Health 에 판본 없는 이름을 줌", SP, 'return {"spec": spec.ref,', 'return {"spec": spec.name,'),
    # ── 실행기(action/executor.py) ──
    ("shadow 가 처리기를 부름", EX, "    if mode == SHADOW:\n        return Execution(command.id, mode, False, None, plan)\n", ""),
    ("모형에 없는 행동을 실행", EX, "    if model.get(command.action) is None:", "    if False:"),
    ("L0 를 명령 id 로 잇지 않음", EX, '"action_ref": command.id}', '"action_ref": None}'),
    ("보고 안 한 결과를 성공으로 메움", EX, 'vals = {k: rep[k] for k in ("is_error", "exit_code", "status_code") if rep.get(k) is not None}', 'vals = {"is_error": False, **{k: rep[k] for k in ("is_error", "exit_code", "status_code") if rep.get(k) is not None}}'),
    ("처리기 결과를 검사하지 않음", EX, '            if bad:\n                raise ContractError("handler", bad)', "            pass"),
    ("관측을 버림", EX, 'obs = list(rep.get("observations") or [])', "obs = []"),
    ("MS 의 tool_error 를 못 읽음", EX, 'any(o.get("signal") == "tool_error" for o in obs)', "False"),
    ("T17 전에도 인자를 넘김", EX, "        if _takes(recorder.action, ARGS_PARAM):", "        if True:"),
    ("T17 뒤에도 인자를 안 넘김", EX, "        if _takes(recorder.action, ARGS_PARAM):", "        if False:"),
    ("원장에 예외 메시지를 남김", EX, '"raised": type(self.raised).__name__ if self.raised else None', '"raised": repr(self.raised) if self.raised else None'),
    # ── 술어 한 벌(action/predicate.py) ──
    ("없는 속성을 비교함", PR, "    if values.get(prop) is None:\n        return False\n    rhs", "    rhs"),
    ("걸린 속성이 없어도 비교함", PR, "    if rhs is None:\n        return False\n", ""),
    ("견줄 수 없으면 참", PR, "    except TypeError:\n        return False", "    except TypeError:\n        return True"),
    ("속성 참조를 막는 자리에서 받음", PR, "        if not refs:", "        if False:"),
    ("이름 없는 술어를 받음", PR, "    if named and (", "    if False and ("),
    ("in 에 목록 아닌 값을 받음", PR, '    if pred[1] in ("in", "not_in") and not isinstance(pred[2], (list, tuple)):', "    if False:"),
    ("props_of 가 겹침을 남김", PR, "            if name not in out:\n                out.append(name)", "            out.append(name)"),
    ("속성 참조의 배수를 버림", PR, 'return ref * v.get("mul", 1)', "return ref"),
    # ── 인자 검사 한 벌(action/params.py) ──
    ("정수 자리의 2.0 을 거절", PA, "            if isinstance(v, float) and v.is_integer():\n                v = int(v)", "            if False:\n                pass"),
    ("수 자리에 참거짓을 받음", PA, '        if isinstance(v, bool) or not isinstance(v, (int, float)):\n            return None, f"{name}: 수가 아니다', '        if not isinstance(v, (int, float)):\n            return None, f"{name}: 수가 아니다'),
    ("required 기본을 거짓으로", PA, 'if ps.get("required", True):', 'if ps.get("required", False):'),
    ("최대를 보지 않음", PA, '        if ps.get("max") is not None and v > ps["max"]:', "        if False:"),
    ("모르는 인자를 받음", PA, 'out = [f"모르는 인자 {k}" for k in args if k not in params]', "out = []"),
    ("enum 에 목록 없이 받음", PA, '        if ps.get("type") == "enum" and not isinstance(ps.get("values"), list):', "        if False:"),
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
