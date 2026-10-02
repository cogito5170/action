# action

L5 EXECUTE 의 저장소(baseline BD-25 · BD-95). 지금은 **꼴(계약)만** 있다: `ActionIntent` · `ActionCommand` · `ActionOutcome`.
실행기 · Guard 는 꼴이 계약 동결된 뒤에 짓는다(baseline `BASELINE.md` §10.2).

- 계약 · L0 대응표 · 표와 다른 점: [`docs/CONTRACT.md`](docs/CONTRACT.md)
- 표준 라이브러리만. Python ≥ 3.10.

```
python3 -m unittest            # 시험. Telemetry 가 옆 디렉터리(또는 TELEMETRY_REPO)에 있으면 L0 catalog 와도 대조한다
python3 eval/mutation.py       # 변이 시험 -- 모두 RED 여야 한다
```

통로: baseline 이슈 [#6](https://github.com/cogito5170/baseline/issues/6). 소유: Action 세션.
