# EXECUTOR — 실행기 설계안 (CMD-A3 · E1 · BD-107)

이 문서는 **제안**이다. baseline 이 BD 로 정한 뒤 E2 로 나눠 지시한다.
이 저장소에 지은 코드(`action/spec.py` · `action/executor.py`)는 접점을 증명하려는 것이다. 부작용이 없고, 다른 저장소의 코드는 그대로다.

읽은 판본은 `STAGES.md` 의 stage-2 다.

| 저장소 | 판본 |
|---|---|
| Telemetry | `d60d591` |
| Sensor | `10bb7ad` |
| MS | `2cb7e61` |
| DC | `ce3a0bc` |
| guard | `6e4ad56` |
| health | `a07d833` |

아래 줄 번호는 이 판본 기준이다.

```
Policy(MS) ─ActionIntent─► Guard(evaluate) ─ALLOW/SAFE_ACTION─► command_material ─+decision_ref·issued_at─► ActionCommand
     ─► execute(command, ActionModel, handlers, recorder, mode) ─► ActionOutcome + 관측(불투명) + L0 action.dispatch/action.result
     ─► Sensor S6 (L0 직접) ─export─► Health.verify(command, verify_args(spec), reads) ─► VerificationRecord
```

---

## 1. 행동 명세의 집

**권고: `action` 저장소에 꼴 `ActionSpec` · `ActionModel`(`action-spec/1` · `action-model/1`)을 두고, 나머지 셋은 그 투영으로 만든다.**
코드: [`action/spec.py`](../action/spec.py).

### 칸

| 칸 | 지금 있는 곳 | 소비자 |
|---|---|---|
| `name` | DC · MS · guard | 모두 |
| `version` | 새 칸. Health `spec` 의 `"이름@판본"`(health `verification.py:111`) | Health |
| `target_model` | MS · guard | Validate · Guard A3 |
| `params` | MS · guard | A4 |
| `preconditions` | MS · guard, 술어 `[속성, 연산, 값]` | A6 |
| `risk` | MS · guard | A7 · D |
| `postcondition` | Health 시험 상수(`{entity, pred}` 의 논리곱) | VERIFY |
| `window_ms` | Health 시험 상수 | VERIFY |
| `description` | MS | CR 의 도구 카드 |

`ActionSpec` 에 **넣지 않는 것**:
- 허가(`grants`) · 막는 위험 등급(`risky`) · 안전 동작 순서(BD-106). 배치마다 다른 운영자 권한과 가정이다. Guard · Model 설정에 둔다.
- 처리기(`handler` · `effect`). 실행 쪽 결합이다. 런타임이 행동 이름으로 붙인다.

### 왜 action 저장소인가

- **소비자 셋이 이미 action 을 받는다.**
  - guard 는 필수 의존이다(guard `pyproject.toml:12`).
  - health 도 필수 의존이다(health `pyproject.toml:12`).
  - MS 는 선택 의존이다(ms `intent.py:36-41`).
- **다른 두 집은 의존 규칙에 걸린다.**
  - Guard 는 Policy(MS)를 import 하지 않는다(BASELINE §10, `BASELINE.md:227`).
  - Guard 는 DC 코드를 import 하지 않는다(BD-102 F5). Health 는 action 계약만 받는다(health `predicate.py:3-4`).
  - 그래서 MS 나 DC 에 집을 두면 셋이 다시 베껴야 한다.
- **guard 의 ActionSpec 은 이미 MS ToolSpec 다섯 칸을 베낀 것이다.** 베끼는 곳이 둘이다: ms `guard_shadow.py:62-66` · guard `eval/ms_contrast.py:74-77`.

### 투영 증명 (`tests/test_spec.py`, 옆 저장소를 두고 돌림)

| 투영 | 시험 |
|---|---|
| `to_ms_tool` | MS `examples/datacenter.json` 의 도구 셋을 `from_tool` → `to_ms_tool` 로 돌린다. `ToolSpec.from_dict` 가 받고, `card()` · `preconditions` 가 원본과 같다 |
| `to_guard_spec` | `guard.ActionSpec(**…)` 가 guard 시험 세계의 `throttle` 과 같다. `GuardModel.from_dict` 가 받는다 |
| `verify_args` | `health.verify(command, **verify_args(spec), …)` 가 VERIFIED 를 낸다. 명령보다 먼저 관측한 값만 있으면 UNKNOWN 이다(health `verification.py:253`) |

### DC 의 `purpose.ActionSpec` 은 다른 개념이다

- DC 의 것(dc `purpose.py:70-74`)은 `name · requires(능력) · meaning` 이다. **목적 단위의 결정 선택지**이고 이름은 대문자(KEEP · RETRY · STOP · ESCALATE)다.
- MS · guard 의 것은 **실행기 행동**이고, 겨냥 · 인자 · 상태 사전조건을 갖는다.
- 둘을 하나로 합치지 않는다. 대신 규칙 하나를 둔다: **실행기로 가는 선택지(`default_decision` 포함)는 ActionModel 의 이름을 가리켜야 한다.** 실행기 밖의 선택지(KEEP · REDUCE · COMPACT)는 ActionSpec 이 아니다(BD-100 (4) · BD-104).
  - 지금 BD-104 가 DENY(D) 로 막는 경우는 기본 행동이 KEEP 이라서 생긴다. 실행기 행동(예: `escalate`)을 가리키게 되면 SAFE_ACTION 이 설 수 있다.
- DC 클래스 이름 `ActionSpec` 을 `DecisionOption` 류로 바꾸는 것은 선택이다(DC 몫). 안 바꾸면 같은 이름이 두 뜻으로 남는다.

### 사후조건 · 창도 같은 집에 넣는다

- 그래야 Health 의 `spec = 이름@판본` 이 사후조건과 같은 판본을 가리킨다.
- 따로 두면 판본이 둘이 되고 서로 흘러간다.

### 술어 · 인자 검사는 지금 세 벌이다

| 벌 | 곳 |
|---|---|
| MS | ms `predicate.py:13-79` · `tools.py:49-65` |
| guard | guard `predicate.py:11-74` · `params.py:10-57` |
| health | health `predicate.py:13-55` |

- 셋을 같게 붙드는 것은 대조 시험이다(guard `test_predicate.py:49-54` · health `test_predicate.py:21-26`).
- E2 에서 **한 벌을 action 으로 옮기고** 셋이 import 한다. 그러면 대조 시험은 같은 것을 확인하는 시험이 된다.
- `ActionSpec` 은 지금 술어의 **모양**만 본다(연산 이름 10 개 = MS `OPS` 8 + exists · missing, 시험이 대조한다).
- **안 고를 때의 비용**: 고칠 때마다 세 벌을 맞추고, 대조 시험 셋을 계속 둬야 한다.

**집을 MS 나 DC 로 둘 때의 비용**: guard · health 가 의존 규칙을 어기거나 다시 베껴야 한다. F1 의 중복(guard `docs/GUARD.md:89`)이 풀리지 않는다.

---

## 2. 실행기 접점

**권고: 실행기는 프로세스 안의 라이브러리 함수다. MS 런타임이 하나뿐인 실행 자리(ms `pipeline.py:139-142`)에서 부른다.**
코드: [`action/executor.py`](../action/executor.py).

```
execute(command, model, handlers, recorder=None, mode="shadow", mono=None) -> Execution
  Execution: command_id · mode · executed · refused · would_dispatch · outcome · observations · raised
```

### 입력 — ActionCommand

ActionCommand 의 재료는 guard `command.py:14-26` 의 `command_material` · `build_command` 다. 그래서 새 코드가 필요 없다. 런타임이 채울 것은 둘이다.

- **`decision_ref`**
  - 지금 ms `runtime.py:139` 의 `before_execute` 가 결정 id 를 런타임의 `pre` 에만 넣는다.
  - 그래서 Pipeline 은 실행 자리에서 그 id 를 모른다. Pipeline 에 id 를 돌려주게 고친다(MS).
- **`issued_at`**
  - MS 시계는 **초**다(ms `cli.py:47-50`). 계약은 unix_ms 다.
  - 곱해서 넣는다(G4). 시각은 ALLOW 시각이고, 실행 시작보다 앞이다.

### 출력

- `ActionOutcome`: 실행기가 본 결과. 보고되지 않은 칸은 None 이다.
- L0 사건 한 쌍: `recorder.action(action, decision_ref, target, action_ref=command_id)`. Telemetry T16 이다(telemetry `recorder.py:132-159`).
- 처리기가 돌려준 **관측(불투명)**: 실행기는 읽지 않고 돌려준다. 런타임이 자기 상태 관리자에 넣는다(ms `pipeline.py:150-157`). PC19 의 G2 를 이렇게 풀었다.

### 처리기 약속

```
handler(target, args) -> {"observations"?, "is_error"?, "exit_code"?, "status_code"?, "output"?}
```

- 칸은 닫혀 있다. 칸이 틀리면 `ContractError` 다. 그것이 **오류로** 기록되고, 성공으로 메우지 않는다.
- `ms_handler(tool.run)` 은 MS 도구를 이 약속으로 감싼다. 결과를 읽는 법은 ms `pipeline.py:146-148` 과 같다(`tool_error` 신호면 `is_error`).
- 예외가 나면:
  - L0 와 결과에는 **종류 이름만** 남는다.
  - 예외 객체는 `raised` 로 돌려준다. MS 는 지금처럼 메시지를 자기 관측(`tool_error`)으로 쓸 수 있다(ms `pipeline.py:143-145`).

### 모드는 둘이다

| 모드 | 처리기 | L0 | 쓰임 |
|---|---|---|---|
| `shadow`(기본) | 부르지 않는다 | 적지 않는다 | 실행될 수 있었는지(행동이 모형에 있나 · 처리기가 붙었나)와 `would_dispatch` 만 돌려준다. 런타임은 지금 길로 실행하고 둘을 견준다 |
| `execute` | 부른다 | `action.*` 한 쌍 | 실제 실행 |

**dry-run 은 모드가 아니다.**
- `execute` 에 바깥에 닿지 않는 처리기를 붙인 것이다. MS 의 `effect` 틀(ms `tools.py:67-77`)이 그런 처리기다.
- 실행기는 처리기가 진짜인지 알 수 없다. 모의인지는 실행(run)의 속성이다(MS `RunRecord.simulated`).
- 이때 L0 기록은 거짓이 아니다. 모의 처리기가 실제로 돌았기 때문이다.

### 닫힌 쪽

아래는 실행하지 않고 L0 에도 적지 않는다.
- 모형에 없는 행동(`UNKNOWN_ACTION`)
- 처리기 없음(`NO_HANDLER`)
- 모르는 모드(`BAD_MODE`)

허가 판정은 여기서 하지 않는다. Guard 를 지난 명령만 온다는 것이 전제다.

### L0 가 없을 때

- 실행기는 `recorder=None` 을 받는다.
- MS 의 `NullRecorder` 에는 `action` 이 없다(ms `l0.py:57-73`). 그 파일은 Telemetry 소유다. E2 에서 Telemetry 가 더하면 MS 의 계측 코드가 한 갈래로 남는다.

### 증거 (`tests/test_executor.py`)

- 진짜 Telemetry `Recorder` 로 적은 두 사건이 `event.check` 를 지난다. 둘 다 `action_ref == command_id` 다. 겨냥은 해시로만 간다.
- shadow 는 사건 0 개, 처리기 호출 0 번이다. 거절도 사건 0 개다.
- 결과를 보고하지 않으면 `is_error` 는 None 이다. 예외는 종류 이름만 남는다.
- 변이 16 개를 더했다(아래 §7).

**안 고를 때의 비용**: 실행기를 따로 프로세스로 두면, 프로세스를 넘는 전송이 처음 생긴다. 그러면 OQ-19(인코딩)를 먼저 정해야 한다.

---

## 3. MS 도구 실행을 `action.*` 으로 바꾸는 시점 (BD-97 Q3)

### 사실

- **지금 Sensor 가 MS 실행의 건강을 읽는 길은 `tool.*` 뿐이다.**
  - Telemetry compat 이 `tool.start` 와 `tool.end` 를 짝지어 `tool_call` 을 만든다(telemetry `compat.py:75-87`). `action.*` 은 **버린다**(`compat.py:12-13`).
  - compat 은 넓히지 않는다(BD-80).
- **그래서 MS 가 지금 `action.*` 만 내면, Sensor 가 MS 실행을 못 본다.** 그 실행(run)에서는:
  - `execution_health` 가 `NO_TOOL_RUN_YET` 이 된다(sensor `execution/__init__.py:128-137`).
  - `tool_execution_health` · `tool_latency` · `tool_outcome_pending` 가 입력을 잃는다.
- MS 시험 `test_l0.py:80-81` 은 `tool.*` 개수를 센다. 이 파일은 Telemetry 소유다.
- **MS 시험의 도구 실행 대부분은 의도가 생기지 않는 길이다.** MS 복사본에서 쟀다(스크래치 계측, 커밋 안 함). 런타임 실행 443 번은 다음과 같다:
  - DC 배선 길(`state_reader`): **43**
  - snapshot 길: **400**
  - 그 밖에 Pipeline 만 쓴 실행이 4 번이다.
  - BD-97 Q1 에 따라 의도(그리고 ActionCommand)는 DC 길에서만 생긴다. 그러니 snapshot 길의 실행은 실행기로 갈 수 없다.

### 권고 순서 — 어느 실행(run)도 같은 실행을 두 사건으로 내지 않는다

1. **Sensor 가 먼저 `action.*` 을 L0 에서 직접 읽는다**(§4). 아직 아무도 `action.*` 을 내지 않으므로 두 번 세지 않는다.
2. Telemetry 가 `NullRecorder.action` 을 더한다. `test_l0` 기대값에 "DC 길 실행 = `action.*`" 을 더한다.
3. MS 의 DC 길에 실행기를 **shadow** 로 붙인다. `would_dispatch` 를 실제 `tool.*` 실행과 견주어 다름 0 을 확인한다.
4. MS 의 **DC 길만** `execute` 로 바꾼다. 그 실행(run)은 `action.*` 만 내고 `tool.*` 은 내지 않는다. snapshot 길은 지금처럼 `tool.*` 을 낸다.
5. E3: Guard enforce.

### BD-97 Q3 과 걸리는 곳 → Request 1

- Q3 은 "MS 의 도구 실행은 `action.*` 으로만" 이다. Q1(의도는 DC 길만)과 함께 보면, snapshot 길의 실행에는 명령을 지을 수 없다.
- 권고: Q3 을 **DC 길 실행** 으로 좁힌다. snapshot 길이 실행을 계속할지는 baseline 이 따로 정한다.
- 좁히지 않을 때의 비용은 둘 중 하나다:
  - `dc_id` 를 nullable 로 바꾼다. 계약 변경이고, BD-97 이 거절했다.
  - snapshot 길에서 실행을 없앤다. MS 시험의 실행 400 번을 고쳐 써야 한다.

---

## 4. Sensor 가 `action.result` 를 읽는 범위

### 지금

| 무엇 | 입력 | 곳 |
|---|---|---|
| `execution_health`(agent) · `tool_execution_health`(tool) | compat 의 `tool_call` | sensor `state/metrics.py:113-181` · `rules.py:234-248` |
| `tool_latency` | compat 의 `tool_call` | `latency/__init__.py:56-63` |
| `execution_interruption` | `tool.end` 의 `timed_out` · `moved_to_background` | `l0.py:94-100` |
| `tool_outcome_pending` | `tool.end` 직접 | `l0.py:89-93` |
| S6 `action_state` | **없다** — 입력 계약만 있다 | `docs/SENSOR_HEALTH_DESIGN.md:222-232` |

- `action` 실체 유형도 없다(`state/model.py:65-70`).
- liveness 는 사건 종류와 무관하게 마지막 사건만 본다(`liveness/__init__.py:138-143`). 바뀌는 것이 없다.

### 권고 (E2 Sensor) — L0 직접 길(`sensing/l0.py`), BD-80

- **S6 `action_state`** 를 짓는다. 실체는 `action:<run>:<command_id>`(BD-32 · BD-99)다. 값은 다음과 같다:
  - STARTED: dispatch 만 있음
  - COMPLETED: result, `is_error=false`
  - FAILED: result, `is_error=true`
  - UNKNOWN: result 는 있으나 `is_error` 를 못 봄
- **실행 건강 지표가 `action.result` 도 센다.** 그 실행(run)의 agent 실체에 대해 `tool_results` · `tool_errors` · `tool_outcome_pending`(dispatch 뿐)을 센다. 뜻은 같다(그 런타임의 실행이 실패했나). 새 상태를 만들지 않는다(BD-79).
- **잃는 것**(`action.result` 에 칸이 없다):
  - `timed_out` · `interrupted` → `execution_interruption`
  - 인자 서명 → `identical_call_max`. 요청 R2 `args_sig` 가 다시 산다. 소비자(A8 · Sensor)가 생겼다.
  - 도구별 실체는 `action_type` 으로 대신할 수 있다(Sensor 가 정한다).
- **Health 가 읽으려면** state-export 의 `subjects` · `entity_ref` 가 `action:` 실체를 알아야 한다(sensor `state/export.py:50-56,82-85`). export 는 DC 소유다(BD-56).

---

## 5. Health VERIFY 가 받을 것

`health.verify(command, *, run, subjects, spec, postcondition, window_ms, reads, evaluated_at, outcome, outcome_ref)` (health `verification.py:262-273`).

| 인자 | 누가 · 어디서 | 비고 |
|---|---|---|
| `command` | 실행기에 들어간 ActionCommand(런타임 원장) | L0 에는 `issued_at` 과 평문 `target` 이 없다(`l0map.NOT_IN_L0`). 그래서 명령 자체를 넘긴다 |
| `run` · `subjects` | 런타임 `run_id`(= L0 `run_id`) · Sensor export `subjects(E, run)` | `subjects.scope == run` 이어야 한다(`verification.py:283-284`) |
| `spec` · `postcondition` · `window_ms` | `verify_args(ActionModel.get(command.action))` | **같은 집**(§1). 시험으로 증명했다 |
| `reads` | `$run.*` → Sensor export `read`. `$target`(MS 세계의 실체, 예 `srv1`) → **MS 상태 관리자를 export 꼴로 읽는 어댑터** | 어댑터는 새 일이다(MS). 세계 상태는 Sensor 에 없다 |
| `evaluated_at` | 런타임 시계(ms) | |
| `outcome` · `outcome_ref` | `Execution.outcome` · L0 result 사건 id | 판정에는 쓰지 않는다(BD-99) |

- **부르는 쪽: 런타임(MS).** 시계와 일정은 Runtime 의 것이다(BASELINE Runtime 행). 두 번 부른다:
  - (a) 실행 직후. 결과 관측이 도착한 때다.
  - (b) 창이 닫힐 때. `issued_at + window_ms`.
  - VerificationRecord 는 `decision_ref` 와 함께 원장에 남긴다. 실체는 `action:<run>:<command_id>` 다.
- **"명령 전 관측은 근거가 아니다"**: 창의 시작은 `command.issued_at` 이다(`verification.py:287`). `observed_at < issued_at` 이면 근거가 아니다(`:253`). `issued_at` 은 ALLOW 시각이고 실행 전이다. 그러니 실행이 낳은 관측은 언제나 그 뒤에 온다.
- **제약(future)**: export 는 지금 값만 준다(`export.py:64-79`). 그래서 재생으로 다시 판정하려면 State 이력 읽기가 필요하다. 실시간 판정에는 지장이 없다.

---

## 6. E2 지시 목록 (제안)

순서: **A4 → (T17 · S-next · D-next 함께) → G-next → M-next shadow → M-next execute → H-next → E3**

| # | 저장소 | 할 일 | 끝난 기준 |
|---|---|---|---|
| A4 | action | `action-spec/1` · `action-model/1` 동결. 술어 · 인자 검사 한 벌을 MS 에서 옮겨 `action/predicate.py` · `params.py` 에 둔다. 실행기를 shadow · execute 로 마감 | 옮긴 술어가 MS · guard · health 의 대조 시험을 그대로 지난다. 변이 RED. guard · health 는 새 sha 로 다시 고정 |
| T17 | Telemetry | `ms/l0.py` `NullRecorder.action` · `test_l0` 에 "DC 길 실행 = `action.*` 한 쌍, `tool.*` 0" 기대를 더한다 | L0 없이도 MS 의 실행기 길이 돈다. L0 가 있으면 DC 길 실행(run)에 `action.*` 2 · `tool.*` 0 이다 |
| S-next | Sensor | S6 `action_state`(L0 직접) · `action` 실체 유형 · 실행 지표가 `action.result` 를 센다 | Telemetry `Recorder` 로 지은 사건(쌍 · dispatch 만 · 오류)이 STARTED · COMPLETED · FAILED 를 낸다. 같은 실행을 `tool.*` 로 낸 경우와 `action.*` 로 낸 경우의 `execution_health` 가 같다(대조 시험) |
| D-next | DC | export `subjects` · `entity_ref` 가 `action:` 실체를 안다. 실행기로 가는 `default_decision` 은 ActionModel 의 이름을 가리킨다 | export `read` 로 `action:<run>:<cmd>` 의 `action_state` 를 읽는다. BD-104 의 D 사례가 실행기 행동이면 SAFE_ACTION 을 낸다 |
| G-next | guard | GuardModel 을 ActionModel 에서 짓는다(`to_guard_spec`). 술어는 action 의 것을 import 한다 | MS 대조 다름 0(지금 68,688 비교) |
| M-next (shadow) | MS | ActionModel 을 spec JSON 에서 읽는다(`tools` → `from_tool`). `before_execute` 가 결정 id 를 Pipeline 에 돌려준다. ActionCommand = guard `command_material` + `decision_ref` + `issued_at`(ms). 실행 자리에서 `execute(…, mode="shadow")` | MS 시험의 DC 길 실행 43 번에서 `would_dispatch` 와 실제 실행(도구 이름 · 겨냥 · 결정 id)의 다름이 0 |
| M-next (execute) | MS | DC 길만 `execute`. `ms_handler(tool.run)`. 관측은 지금처럼 ingest. snapshot 길은 그대로 | DC 길 실행(run)이 `action.*` 만 낸다. MS 시험이 초록(Telemetry 기대 고침 포함). Sensor 의 `execution_health` 가 바꾸기 전과 같다 |
| H-next | health + MS | 런타임이 실행 직후와 창이 닫힐 때 `verify` 를 부른다. `reads` 어댑터(MS 세계 상태 → export 꼴) | 대본 세계에서 VERIFIED · NOT_VERIFIED · PENDING → UNKNOWN 이 나온다. 레코드가 원장에 `decision_ref` 와 함께 있다 |
| E3 | guard | enforce(BD-106 순서를 Model 설정에) | E2 가 모두 통합된 뒤 |

---

## 7. 이 저장소에서 한 것과 검증

- **새 코드**:
  - `action/spec.py`: ActionSpec · ActionModel · 투영 셋
  - `action/executor.py`: `execute` · `ms_handler`
  - `tests/siblings.py`: 옆 저장소 찾기(`<이름>_REPO`)
- **동결된 꼴 셋은 그대로다**(`action-contract/1`, GOLDEN 해시 그대로).
- **시험 50**:
  - 옆 저장소(Telemetry · MS · guard · health)를 두면 건너뜀 0 이다.
  - 옆 저장소가 없으면 대조 9 개를 까닭과 함께 건너뛴다.
- **변이 41/41 RED.** 앞의 25 개는 그대로이고, 명세 9 개 · 실행기 7 개를 더했다.
- **변이 도구의 결함을 찾아 고쳤다.**
  - 결함: 같은 임시 디렉터리에서 변이를 차례로 돌리면, 같은 초에 쓴 같은 크기의 변이가 낡은 `.pyc` 를 다시 쓸 수 있었다. 그러면 헛 RED 가 난다.
  - 고침: 이제 `python -B` 로 돈다.
  - A1 의 25 개를 `-B` 로 다시 돌렸고 모두 RED 다. 결함이 드러낸 군더더기 한 줄(예외 뒤 `obs = []`)은 지웠다.
- **옆 저장소 시험**: 이 코드를 옆에 두고 guard · health · MS 시험을 다시 돌렸다. 모두 초록이다(MS 는 건너뜀 2 개로, 바꾸기 전과 같다).
