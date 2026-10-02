# action

L5 EXECUTE 의 저장소(baseline BD-25 · BD-95 · BD-108).

- 꼴: `ActionIntent` · `ActionCommand` · `ActionOutcome`(`action-contract/1`) · `ActionSpec` · `ActionModel`(`action-spec/1` · `action-model/1`).
- 술어 · 인자 검사 한 벌, 실행기(shadow · execute).

- 계약 · L0 대응표 · 표와 다른 점: [`docs/CONTRACT.md`](docs/CONTRACT.md)
- 실행기 설계(BD-108): [`docs/EXECUTOR.md`](docs/EXECUTOR.md) · 행동 명세 `action-spec/1`(CONTRACT §6) · 실행기 `action/executor.py`
- SDK 설계안(S1, 제안): [`docs/SDK.md`](docs/SDK.md) — 시제품 `sdk_draft/`(action 패키지 밖, 옆 저장소가 있어야 돈다)
- 술어 · 인자 검사 한 벌: [`docs/PREDICATE.md`](docs/PREDICATE.md) · `eval/predicate_swap.py`(MS · guard · health 복사본에서 바꿔 끼워 전체 시험)
- 표준 라이브러리만. Python ≥ 3.10.

```
python3 -m unittest            # 시험. 옆 저장소(Telemetry · MS · guard · health, 또는 <이름>_REPO)가 있으면 대조한다
python3 eval/mutation.py       # 변이 시험 -- 모두 RED 여야 한다
```

통로: baseline 이슈 [#6](https://github.com/cogito5170/baseline/issues/6). 소유: Action 세션.
