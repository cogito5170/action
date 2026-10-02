# action

L5 EXECUTE 의 저장소(baseline BD-25 · BD-95). 지금은 **꼴(계약)만** 있다: `ActionIntent` · `ActionCommand` · `ActionOutcome`.
실행기 · Guard 는 꼴이 계약 동결된 뒤에 짓는다(baseline `BASELINE.md` §10.2).

- 계약 · L0 대응표 · 표와 다른 점: [`docs/CONTRACT.md`](docs/CONTRACT.md)
- 실행기 설계안(E1, 제안): [`docs/EXECUTOR.md`](docs/EXECUTOR.md) — `action/spec.py` · `action/executor.py` 는 접점 증명용(부작용 없음)
- 표준 라이브러리만. Python ≥ 3.10.

```
python3 -m unittest            # 시험. 옆 저장소(Telemetry · MS · guard · health, 또는 <이름>_REPO)가 있으면 대조한다
python3 eval/mutation.py       # 변이 시험 -- 모두 RED 여야 한다
```

통로: baseline 이슈 [#6](https://github.com/cogito5170/baseline/issues/6). 소유: Action 세션.
