# CONTRACT — Action 꼴 셋 (`action-contract/1`)

근거: baseline `claude/gracious-meitner-vp49xe` 의 BD-25 · BD-95 · `SCHEMA_PROPOSAL.md` §2.6 · `BASELINE.md` §10.2 · 이슈 baseline#6 의 CMD-A1.
코드: [`action/forms.py`](../action/forms.py) · [`action/canonical.py`](../action/canonical.py) · [`action/l0map.py`](../action/l0map.py).

```
Policy(MS) ─ActionIntent─► [Validate · Arbitrate · Guard] ─ActionCommand─► Executor ─► L0 action.dispatch / action.result
                                                                                       (ActionOutcome = action.result 의 칸)
```

## 1. 꼴

모든 꼴은 **닫혀** 있다: `from_dict` 는 모르는 칸 · 빠진 칸 · 다른 판본을 거절한다(`ContractError`). 칸마다 타입 · 값을 지을 때 검사한다.
`schema` 칸이 판본이다. 꼴이 바뀌면 판본을 올린다(시험의 GOLDEN 해시가 바뀐다).

### ActionIntent (`action-intent/1`) — DECIDE 의 출력. 실행 요청 **제안**

| 칸 | 타입 | 뜻 |
|---|---|---|
| `intent_id` | `int-` + 16 hex | **내용 해시**(아래 칸 전부). 받는 쪽이 다시 계산해 맞지 않으면 거절 |
| `dc_id` | str(빈 것 아님) | 이 결정이 본 DecisionContext id |
| `policy` | `"<이름>@<판본>"` | 표의 `policy@ver` |
| `action` | str(빈 것 아님) | ActionSpec(Model) 이름 |
| `target` | str \| null | 겨냥 실체. 겨냥 없는 행동(STOP · ESCALATE)은 null |
| `args` | JSON 객체 | |
| `rationale` | str(빈 것 허용) | |
| `used_keys` | [str] | 결정이 쓴 DC 키. **집합** — 정렬해 싣는다, 겹치면 거절 |
| `author_kind` | `rule` · `llm` · `human` | |
| `schema` | `action-intent/1` | |

### ActionCommand (`action-command/1`) — GUARD 가 허가한 명령. 실행기는 이것만 받는다

| 칸 | 타입 | 뜻 |
|---|---|---|
| `command_id` | `cmd-` + 16 hex | 내용 해시 |
| `intent_id` | `int-` + 16 hex | 어느 의도에서 |
| `decision_ref` | str(빈 것 아님) | **표에 없던 칸**(§3 D1). 이 명령을 낸 결정 기록(MS `DecisionRecord.id`) |
| `action` | str | 의도의 action 과 다를 수 있다(SAFE_ACTION) |
| `target` · `args` | 위와 같다 | |
| `issued_at` | 수, unix_ms, ≥ 0 | |
| `deadline` | 수 \| null, unix_ms, > `issued_at` | 실행 기한. 검증 시간 창은 ActionSpec 의 것(BD-31) |
| `schema` | `action-command/1` | |

### ActionOutcome (`action-outcome/1`) — 실행기가 본 결과. **원장이 아니다** — L0 `action.result` 의 칸 그대로

| 칸 | 타입 | L0 출처 종류 |
|---|---|---|
| `command_id` | `cmd-` + 16 hex | ref (`action_ref`) |
| `is_error` | bool \| null | reported |
| `exit_code` · `status_code` | int \| null (bool 거절) | reported |
| `exception` | 예외 **종류 이름** \| null — 메시지는 거절 | reported |
| `output_chars` | int ≥ 0 \| null | measured |
| `elapsed_ms` | 수 ≥ 0 \| null | measured |
| `schema` | `action-outcome/1` | |

null = **못 봤다**. 기본값으로 메우지 않는다(결과 없음은 성공도 실패도 아니다). 판정(성공 · 실패 · VERIFIED)은 이 꼴에 없다 — Sensor(S6) · VERIFY 의 일.
ActionOutcome 에는 id 칸이 없다(관측이다). 내용 해시가 필요하면 `digest()`.

## 2. 정준 JSON · 해시

- `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)` → UTF-8 → sha256 앞 16 hex.
  MS `decision_record.py` 와 같은 방식이고, 다른 점은 둘: 구분자 고정 · `default=str` 없음(JSON 이 아닌 값 · NaN · 무한대는 거절).
- `1` 과 `1.0` 은 다른 글이므로 다른 해시다. 보내는 쪽이 수의 꼴을 고정해야 한다(시험 `test_int_and_float_are_distinct`).
- 같은 내용 → 같은 id. 같은 DC · 같은 정책에서 같은 의도를 두 번 내면 id 가 같다(의도의 정체성은 내용이다). 명령은 `issued_at` 이 달라 다르다.

## 3. SCHEMA_PROPOSAL 표와 다른 점 (baseline 판단 필요)

| # | 표 | 여기 | 까닭 |
|---|---|---|---|
| D1 | ActionCommand 에 `decision_ref` 없음 | **더함** | L0 `action.dispatch.decision_ref` 를 실행기가 채워야 한다. 의도는 결정 기록보다 **먼저** 생기므로(MS DecisionRecord 는 중재 결정을 담는다) 의도가 결정 id 를 가질 수 없다. 허가 뒤의 명령이 갖는 것이 자연스럽다. 새 원장은 없다 |
| D2 | `policy@ver` | 칸 `policy`, 값 `"<이름>@<판본>"` | 칸 이름에 `@` 를 쓰지 않으려고. 뜻은 같다 |
| D3 | ActionOutcome `error` | `exception` | L0 `action.result.exception` 과 같은 이름. 같은 것에 이름 둘(DUP)을 두지 않는다 |
| D4 | `intent_id` · `command_id` 는 칸 | 칸이지만 **내용 해시**로 정해진다 | MS DecisionRecord 와 같은 방식. 고쳐짐을 받는 쪽이 안다. 대신 같은 내용의 의도는 같은 id |
| D5 | (없음) | 각 꼴에 `schema` 칸 | 판본 요구(CMD-A1) |

## 4. L0 대응표

L0 칸은 Telemetry `70b4feb` `telemetry/catalog.py` 에서 베꼈다(`l0map.L0_FIELDS`). Telemetry 가 옆에 있으면 시험이 지금 catalog 와 대조한다.

### `action.dispatch` ← ActionCommand (실행 시작)

| L0 칸 | 출처 | 옮기는 법 |
|---|---|---|
| `action_ref` | `command_id` | 그대로 |
| `decision_ref` | `decision_ref` | 그대로 |
| `action_type` | `action` | 실행기가 **실제로** 실행한 이름(보통 같다) |
| `target` | `target` | `#` + Telemetry 열쇠 해시(12 hex). 평문은 L0 로 가지 않는다. null → null |

### `action.result` ← ActionOutcome (실행 끝)

`action_ref` ← `command_id`, 나머지 여섯 칸은 같은 이름 그대로. null 은 L0 에서 `unobserved`.

### L0 로 가지 않는 것

| 칸 | 까닭 |
|---|---|
| ActionIntent 전부 | 결정이다. L0 는 결정을 싣지 않는다(TELEMETRY.md 6 · 7 절) |
| `ActionCommand.intent_id` | 결정 쪽 식별자. L0 는 `decision_ref` 하나로 잇는다 |
| `ActionCommand.args` | 인자 평문은 L0 에 싣지 않는다 → 요청 R2 |
| `ActionCommand.issued_at` | L0 봉투 `at` 이 dispatch 를 본 시각 |
| `ActionCommand.deadline` | 우리 기한은 L0 에 없다 → 요청 R1 |

### 요청: Telemetry (빠진 칸 · 맞지 않는 곳)

| # | 무엇 | 왜 | 급함 |
|---|---|---|---|
| R0 | `Recorder.action(...)` 이 `action_ref` 를 **받을 수 있게**. 지금은 `f"{run_id}/a{n}"` 를 스스로 만든다 | `action_ref = command_id` 여야 L0 사건에서 명령 · 의도 · 결정으로 거슬러 갈 수 있다. 지금 Recorder 를 쓰면 실행기가 command_id 를 L0 에 실을 길이 없다 | 실행기 전에 |
| R1 | `action.dispatch.deadline_ms`(declared) | 실행기가 **스스로 선언한** 기한. Sensor 가 "기한 지났는데 결과 없음" 을 L0 만으로 가를 수 있다. 없으면 기한을 모른다 | 선택 |
| R2 | `action.dispatch.args_sig`(measured, 열쇠 해시) | 같은 명령 되풀이(A8 계열) 탐지. `tool.*.tool_sig` 와 같은 방식 | 선택 |

또 하나(정보): Telemetry `recorder.py` 머리 주석의 예 `rec.action("RETURN", decision_ref=dc_id)` 는 `decision_ref` 에 **DC id** 를 넣는다.
TELEMETRY.md 와 MS 는 `decision_ref = DecisionRecord.id` 다. 이 계약은 뒤의 것을 따른다.

## 5. 범위

지은 것: 꼴 셋 · 정준 JSON · 대응표(데이터 + 사건 칸을 채우는 두 함수). 짓지 않은 것: 실행기 · Guard · 네트워크 · L0 Recorder 배선.
표준 라이브러리만(OQ-19). MS · Telemetry 파일은 고치지 않았다.
