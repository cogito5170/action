"""옆 저장소 찾기 -- 대조 시험용. `<이름>_REPO` 환경 변수, 없으면 이 저장소 옆의 디렉터리(이름의 여러 표기).
찾지 못하면 None -- 그 시험은 까닭을 남기고 건너뛴다(baseline 통합은 모두 옆에 두고 돌린다)."""
import importlib
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent


def repo(name: str, package: str):
    env = os.environ.get(f"{name.upper()}_REPO")
    cands = [pathlib.Path(env)] if env else []
    cands += [HERE.parent / n for n in (name, name.lower(), name.capitalize(), name.upper())]
    for c in cands:
        if (c / package / "__init__.py").exists():
            return c
    return None


def load(name: str, package: str, module: "str | None" = None):
    """옆 저장소의 모듈. 없으면 None."""
    root = repo(name, package)
    if root is None:
        return None
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return importlib.import_module(module or package)
