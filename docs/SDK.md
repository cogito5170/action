# SDK — 설계안 (CMD-A7 · S1 · BD-119)

이 문서는 **제안**이다. baseline 이 BD 로 정한 뒤 S2 로 나눠 지시한다.

이 저장소에 지은 시제품(`sdk_draft/autonomy.py` · `sdk_draft/hooks.py`)은 접점을 증명하려는 것이다.
- 부작용이 없다. 원장 · L0 는 주지 않으면 쓰지 않고, 처리기는 MS 의 effect 틀(모의)이다.
- `action` 패키지 밖에 두었다. action 패키지는 그대로다(guard · health 의 고정 `3995fdb` 와 패키지 코드가 같다).

읽은 판본은 `STAGES.md` stage-3 다. 아래 줄 번호는 이 판본 기준이다.

| 저장소 | 판본 |
|---|---|
| Telemetry | `89d2887` |
| Sensor | `a073e77` |
| MS | `74a8585` |
| DC | `b55ff04` |
| guard | `be871b9` |
| health | `afcff39` |
| action | `2f4791e` |

일곱 저장소를 옆에 두고 기준선을 다시 돌렸다: 72 · 246 · 212 · 108 · 93 · 36 · 68, 모두 초록.

```
사용자 ─► Autonomy.handle(task)                                       (새 저장소 autonomy, §6)
            └► MS Runtime.handle ─► DC(MSStateReader) ─► LLM 제안 ─► Arbiter ∧ Guard ─► 실행기(action) ─► L0 action.*
                                                                                                └► Health.verify ─► 원장
남의 에이전트(Claude Code · Agent SDK) ─PreToolUse─► HookAdapter ─► Guard ─► deny | {}
                                     ─PostToolUse(Failure)─► observe ─► (transcript → Telemetry cc_jsonl → Sensor)
```

---

## 1. 입구

**권고: 새 조립자를 짓지 않는다. MS `Runtime` 을 감싸는 얇은 층 `Autonomy` 하나를 둔다.**
시제품: [`sdk_draft/autonomy.py`](../sdk_draft/autonomy.py).

```python
a = Autonomy.from_spec(spec, observations, actions=tools, llm=provider,      # 반드시 받는 것: 세계 · 행동 · LLM
                       purpose="context_runtime", guard_mode="shadow",        # 기본값이 있는 것
                       grants=(), l0=None, ledger=None, run_state=None, clock=None)
a.open_session("s", {"token_budget": 1000})
r = a.handle("srv07 을 throttle", queries=spec["queries"])   # → Result(outcome · decision_id · guards · executions · verifications · raw)
a.close_windows()                                            # 창이 닫힌 VERIFY 마감
Autonomy.versions()                                          # 동결 계약의 판본(§3)
```

**반드시 받는 것은 셋이다.**
- 세계: MS `StateManager`, 또는 명세 + 관측.
- 행동: 도구 정의 목록(행동 명세 + 처리기).
- LLM.

**기본으로 채우는 것**:

| 무엇 | 기본 | 까닭 |
|---|---|---|
| 결정 문맥 | **DC 길**(`MSStateReader`, 목적 `context_runtime`) | 아래 참고 |
| `guard_mode` | `"shadow"` | BD-118 |
| L0 | 끔 | `l0=` 에 경로(`JsonlSink`) 또는 sink 를 주면 켠다 |
| 원장 | 끔 | `ledger=` 를 주면 켠다 |
| `run_state` | None | `$run.*` 사후조건이 생길 때 Sensor 를 꽂는다(BD-115 (1)) |

**DC 길을 기본으로 하는 까닭**: 의도 · Guard · 실행기 · VERIFY 는 결정 문맥 id 가 있을 때만 돈다(ms `intent.py:48-52` · `runtime.py:152`).
- 지금 `ms ask` 는 `state_reader` 없이 snapshot 길로 돈다(ms `cli.py:193-215`). 그러면 이 넷이 하나도 지나지 않는다.
- 그래서 SDK 는 snapshot 길을 내놓지 않는다. BD-114 (2)(enforce 에서 snapshot 길은 실행하지 않는다)와 같은 쪽이다.

**새 조립자를 지을 때의 비용**:
- Runtime 이 이미 하는 순서를 다시 지어야 한다: Guard · 실행기 · VERIFY 조립(ms `runtime.py:84-96`), 실행 직전 결정 기록, A8 기억, VERIFY 창.
- 그것을 지키는 MS 시험 212 개를 다시 써야 한다(DUP).

**증거** `tests/test_sdk_draft.py::Loop`: 예시 세계(`ms/examples/datacenter.json`)에서 한 바퀴를 shadow · enforce 두 모드로 돌렸다.
- 결정의 `state_source` 가 `dc-…` 다.
- Guard ALLOW 다. `mode` 칸이 입구에 준 모드와 같다.
- 실행기가 `throttle srv07` 를 실행했다. 명령의 `decision_ref` 가 결정 id 와 같다.
- VERIFY 는 `VERIFIED/MET` 다.
- L0 의 행동 사건은 `action.dispatch` · `action.result` 한 쌍뿐이다(`tool.*` 0). `action_ref` 가 `command_id` 와 같다.
- 원장 파일은 쓰지 않았다.

## 2. 사용자가 꽂는 자리

| 자리 | 지금의 이음매 | 꼴 | SDK 에서 |
|---|---|---|---|
| 도구 처리기 + 행동 명세 | ms `ToolRegistry(tools)` `tools.py:79`, 처리기 `.bind` `:112`. 명세는 `ActionSpec.from_tool` → `to_ms_tool`(`tools.py:87-102`, action `spec.py`) | 도구 dict: `name · target_model · risk · params · preconditions · postcondition · window_ms · description` + 처리기 `(target, args) -> [{signal, value[, entity, ts]}]`(`tools.py:10-11`). 처리기가 없으면 `effect` 틀(모의) | `actions=` |
| LLM 공급자 | ms `LLMProvider` `providers/base.py:82`(`generate` `:117` · `collect` `:148`) · `make_provider(name)` `providers/__init__.py:28` · `CallableProvider` `:48` · `ScriptedLLM` `llm.py:108`. 글 → 글 함수는 자동으로 감싼다(`pipeline.py:75`) | `CanonicalRequest → CanonicalResponse` | `llm=` |
| 목적 | DC `Purpose` `purpose.py:77-88`. 내장 여섯은 `PURPOSES` `:253`. 등록은 `DecisionContextBuilder(sources, purposes=…)` `builder.py:53-55` | `Purpose(name, version, refs, constraints, actions, query_sources, default_decision)` | `purpose=`(이름). 새 목적을 꽂는 칸은 S2 |
| 문턱(Model) | MS 세계 모형 `models[].derived`(datacenter.json:85-110 · ms `model.py:145-160`) · Sensor `StateConfig`(llmsensor `state/config.py:25-45`) | 명세 JSON · `StateConfig(...)` | 세계 명세로 들어온다. 사용량 문턱은 하드코딩이다(ms `usage_model.py:36-37, 97-125`) → **꽂을 수 없다**(S2 후보) |
| Guard 위험 등급 | guard `GuardModel.from_action_model(…, risky=)` `views.py:154-162` | 위험 등급 목록 | **MS 가 `risky` 없이 짓는다**(ms `guard_shadow.py:62-66`) → 런타임에서 꽂을 수 없다(S2-1) |
| `guard_mode` | ms `Runtime(guard_mode=)` `runtime.py:74, 87-92` | `"shadow"` · `"enforce"`(guard 가 없으면 런타임이 서지 않는다) | `guard_mode=` |
| 허가 | ms `Runtime(grants=)` → Arbiter `:84` · Guard `:90` | 도구 이름들 | `grants=` |
| L0 기록 위치 | ms `Runtime(l0_ledger= \| l0_sink=)` `runtime.py:109-112` → `ms/l0.py:39-46`(Telemetry `Recorder`) | 경로 또는 `.write(ev)` 하는 sink(telemetry `ledger.py:12-28`) | `l0=` |
| 결정 원장 | ms `Runtime(ledger_path=)` `runtime.py:380-383` | JSONL 경로 | `ledger=` |
| `$run.*` 읽기 | ms `Runtime(run_state=)` `verify.py:16-19, 70-81` | `.read(entity, state)` · `.subjects(run)` | `run_state=`. Sensor 어댑터는 아직 없다(S2-3) |

## 3. 공개 경계와 판본

**공개는 셋뿐이다. 나머지는 내부다.**

1. **입구**: `Autonomy` · `Result`.
2. **꽂는 자리의 약속**(§2):
   - 도구 dict · 처리기 서명
   - `LLMProvider`
   - `Purpose`
   - `StateConfig`
3. **동결된 계약**(데이터 꼴). SDK 가 다시 내보내고, `Autonomy.versions()` 가 판본을 돌려준다.

| 계약 | 판본 | 결정 |
|---|---|---|
| ActionIntent · ActionCommand · ActionOutcome | `action-contract/1` | BD-96 |
| ActionSpec · ActionModel | `action-spec/1` · `action-model/1` | BD-109 |
| GuardResult · ValidationResult | `guard-result/1` · `validation-result/1` | BD-102 |
| VerificationRecord | `verification-record/1` | BD-101 |
| L0 사건 | `l0-telemetry/1` | — |
| Sensor 상태 읽기 | `llmsensor.state-export/2` | — |

**내부**(사용자가 import 하지 않는다): Runtime 속 · Pipeline · CR · Arbiter · DC builder 속 · Sensor 엔진 · 수집기.
- 일곱 저장소는 내부를 자유롭게 바꾼다.
- 공개 경계가 바뀌는 것만 판본을 올린다.

**판본 규칙**:
- SDK 는 semver 다. S2 동안은 `0.x` 다.
- 일곱 저장소의 sha 를 **판본 목록(manifest) 하나**에 고정한다(BD-68 · BD-92 방식). SDK 시험이 `versions()` 가 그 목록과 같은지 붙든다.
- 계약은 판본을 올려 **더하는 쪽으로만** 바뀐다(BD-96).
- SDK 판본은 이렇게 올린다:

| 무엇이 바뀌었나 | SDK 판본 |
|---|---|
| 노출한 계약의 판본이 호환되지 않게 바뀜 | major |
| 꽂는 자리 · 공개 이름을 더함 | minor |
| 계약을 바꾸지 않는 sha 갱신 | patch |

## 4. 배포

**권고**:
- 지금처럼 **git sha 고정**으로 간다.
- 묶음 패키지 **하나**(`autonomy`)를 두고, 그 안에서 일곱을 sha 로 고정한다.
- 선택 설치(extras)는 `sensor` 하나만 둔다.

| 갈림길 | 권고 | 고르지 않은 쪽의 비용 |
|---|---|---|
| git sha 고정 대 패키지 저장소(PyPI) | git sha | PyPI 에 올리려면 일곱을 모두 먼저 올리고 판번호 · 출시 절차를 일곱 번 둬야 한다. 공개 색인은 직접 참조(`name @ git+…`) 의존을 받지 않는 것으로 안다(PEP 440) — **확인 못 함**(이 환경에서 peps.python.org · packaging.python.org 가 막혀 있다) |
| 묶음 하나 대 저장소마다 | 묶음 하나(`autonomy`) | 저장소마다 설치하게 하면 사용자가 일곱의 호환 sha 짝을 스스로 맞춰야 한다 |
| guard · health 를 필수로 대 선택(extras)으로 | **필수** | 지금 MS 는 guard · health 가 import 되느냐로 행동이 조용히 바뀐다(ms `runtime.py:90, 95`). 선택으로 두면 같은 코드가 설치에 따라 다르게 돈다. enforce 는 어차피 guard 가 있어야 선다 |
| Sensor 를 필수로 대 선택 | **선택**(`autonomy[sensor]`) | 필수로 하면 입구 한 바퀴에 쓰이지 않는 의존(Sensor 246 시험 · Telemetry 고정)이 늘 따라온다. Sensor 는 훅 길과 `$run.*` 에서만 쓴다 |
| 훅 어댑터의 의존 | 없음(표준 라이브러리) | 어댑터는 dict 를 받아 dict 를 낸다. `claude-agent-sdk` 는 사용자 쪽 의존이다. SDK 가 그것을 요구하면 OQ-19(표준 라이브러리만)와 부딪힌다 |

## 5. 에이전트 SDK 훅 어댑터

### 공식 문서로 확인한 것

원문을 읽었다:
- `https://code.claude.com/docs/en/hooks.md`(Claude Code hooks reference) — 아래 줄 번호는 이 파일 기준이다
- `https://code.claude.com/docs/en/agent-sdk/hooks`
- `https://code.claude.com/docs/en/agent-sdk/python`

| 무엇 | 확인한 꼴 | 출처 |
|---|---|---|
| 도구 앞 · 뒤 사건 | `PreToolUse` · `PostToolUse`(성공) · `PostToolUseFailure`(실패). Python SDK 와 TypeScript SDK 모두 지원 | agent-sdk/hooks "Available hooks" 표 |
| PreToolUse 입력 | `session_id · transcript_path · cwd · permission_mode · hook_event_name · tool_name · tool_input · tool_use_id`(공통 칸에 `prompt_id` 등도 있다) | hooks.md "PreToolUse input" 예 · Python `PreToolUseHookInput` |
| 막는 법 | `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": …}}`. 값은 `allow · deny · ask · defer` | hooks.md:1791-1821 |
| `allow` 의 뜻 | **권한 확인을 건너뛴다**(일부 예외). deny · ask 규칙은 그래도 평가된다 | hooks.md:1797 |
| 여러 훅이 다를 때 | 우선순위 `deny > defer > ask > allow` | hooks.md:1802 · agent-sdk/hooks Note |
| 종료 코드 2 | `"deny"` 와 같은 길로 막는다. stderr 가 까닭이 된다 | hooks.md:1804 |
| PostToolUse 입력 | `tool_input` · **`tool_response`**(도구가 돌려준 결과) · `tool_use_id` · `duration_ms`(선택) | hooks.md:1985-2012 · Python `PostToolUseHookInput.tool_response: Any` |
| PostToolUseFailure 입력 | `tool_name · tool_input · tool_use_id · error`(문자열; Bash 는 첫 줄 `Exit code N`) · `is_interrupt`(선택) · `duration_ms`(선택) | hooks.md:2091-2125 |
| PostToolUse 출력 | `decision: "block"`(+`reason`) · `additionalContext` · `updatedToolOutput` | hooks.md:2014-2025 |
| Agent SDK(Python) 등록 | `ClaudeAgentOptions(hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[cb])]})`. 콜백은 `async def cb(input_data, tool_use_id, context) -> dict`. `{}` 를 돌려주면 허락이다 | agent-sdk/hooks "Configure hooks" · "Callback functions" |
| 시간 초과 | PreToolUse 콜백이 시간을 넘기면 **도구를 실행하지 않는다**. 기본은 600 초 | agent-sdk/hooks "Hook timeout" |
| 훅 종류(Claude Code 설정) | `command · http · mcp_tool · prompt · agent` | hooks.md "Hook types" |

**확인하지 못한 것**:
- Python SDK 의 `PostToolUseFailureHookInput` 타입 정의. 참조 페이지에 없었다(hooks.md 의 입력 예는 확인했다).
- `PostToolUse` 가 불릴 때 transcript 파일에 그 도구 결과가 **이미 써져 있는지**. 문서에 없다 → S2 실험(S2-2).

### 설계

**시제품**: [`sdk_draft/hooks.py`](../sdk_draft/hooks.py). 순수 함수이고, 판정은 주입받는다.

**PreToolUse → Guard.**
- 의도 칸(`intent_material`):
  - `action` = `tool_name`
  - `args` = `tool_input`
  - `target` = None(Claude Code 도구에는 MS 세계의 실체가 없다)
  - `rationale` = ""(훅 입력에 없다. 지어내지 않는다)
- `judge(intent) -> GuardResult` 가 `guard.evaluate` 를 부른다. 세 입력이 필요하다:
  - **DCView**: 결정 문맥. 목적은 `execution_control`(DC `purpose.py:203`)을, 그 세션의 Sensor 상태 위에서 짓는다.
  - **StateView**: 겨냥이 없으니 비어 있어도 된다.
  - **GuardModel**: 에이전트 도구들(Bash · Write · Edit …)의 `ActionModel`. 위험 등급과 인자는 운영자 설정이다.
- **guard 에는 DC 없이 판정하는 길이 없다.** A0 가 `dc_id` 가 맞는지 본다(guard `rules.py:79-80`).
- 출력 규칙:
  - shadow: 기록만 하고 늘 `{}`.
  - enforce: ALLOW 가 아니면 deny.
  - **ALLOW 에도 `"allow"` 를 내지 않고 `{}`.** `"allow"` 는 사용자의 권한 확인을 건너뛰므로(hooks.md:1797) Guard 가 허가를 **넓히게** 된다. Guard 는 닫는 쪽으로만 쓴다(BD-07).
  - 판정 중 예외: enforce 에서 deny(까닭은 예외 종류만), shadow 에서 `{}`.
  - 우리 deny 는 다른 훅의 allow 를 이긴다(우선순위, hooks.md:1802).
- 입구는 둘이다:
  - Claude Code 명령 훅: `run_command_hook`. 표준입력 JSON → 표준출력 JSON, 종료 0.
  - Agent SDK 콜백: `HookAdapter.callback`.

**PostToolUse · PostToolUseFailure → 관측.**
- 권고는 **(b) 어댑터가 L0 를 직접 쓰지 않는 것**이다. 대신 훅 입력의 `transcript_path` 를 Telemetry 의 `from_cc_jsonl` 로 다시 거둔다(Telemetry `collect/__init__.py:245-246`). 그것을 Sensor 에 넣는다.
- 그러면 **L0 를 쓰는 쪽이 하나**(cc_jsonl)로 남는다. 한 사실은 한 사건이다(BD-97 Q3).

| 갈림길 | 권고 | 고르지 않은 쪽의 비용 |
|---|---|---|
| (a) 훅이 `tool.start` · `tool.end` 를 직접 낸다 대 (b) transcript 를 다시 거둔다 | **(b)** | (a) 의 비용은 넷이다:<br>① cc_jsonl 과 함께 돌면 같은 도구 호출이 두 사건이 된다(DUP).<br>② L0 `tool.*` 에는 `tool_use_id` 칸이 없다. 수집기는 순번(`tool_index`)만 낸다(telemetry `collect/__init__.py:164, 167`).<br>③ 훅에는 어느 LLM 호출의 도구인지(`call_index`)가 없다. Sensor 는 모형 호출 아래에 없는 `tool_call` 을 버린다(llmsensor `normalize.py:106-110`). 그래서 상태가 서지 않는다.<br>④ 명령 훅은 매번 다른 프로세스라 순번을 이어 셀 곳이 없다. |
| (b) 의 비용 | — | 호출마다 transcript 전체를 다시 읽는다(O(n)). Sensor 도 접두마다 엔진을 다시 짓는다(llmsensor `eval/first_eval.py:9-11, 55-61`). 긴 세션에서는 늦다 → 늘려 읽기(`since=`)가 S2 후보다 |

**Telemetry 수집기와 겹치는 곳**:
- 같은 transcript 를 읽는다. 훅은 **언제** 다시 거둘지 알려 주는 신호일 뿐이다.
- Guard 기록(`tool_use_id`)과 L0 도구 사건(`tool_index`)을 잇는 열쇠가 L0 에 없다. 수집기는 안에서 `tool_use_id` 로 짝짓고 있다(`collect/__init__.py:127`). 그러니 ref 칸 하나를 **더하기**로 실으면 잇는다(S2-2).

**서명 열쇠**:
- `tool_sig` · `args_sig` 의 열쇠는 `TELEMETRY_HASH_KEY` 가 없으면 프로세스마다 무작위다(telemetry `hashing.py:22-37`).
- 명령 훅은 매번 다른 프로세스다. 그러니 SDK 가 열쇠를 환경으로 주어야 되풀이(A8 · `identical_call_max`)를 잡는다.

**증거** `tests/test_sdk_draft.py::Hooks`(8 개). 진짜 guard · 공식 문서의 입력 예 그대로:
- enforce · 허가 없음 → 문서 꼴의 deny(까닭에 `A7`).
- 허가 있음 → `{}`. `"allow"` 를 내지 않는다.
- shadow → `{}`, 기록에는 DENY.
- 모르는 인자 → A4 deny.
- 판정 오류 → enforce 에서만 deny, 메시지는 새지 않는다.
- 실행 뒤 훅 둘 → 관측만 넘기고 판정은 없다.
- 명령 훅 표준입력 · 표준출력, Agent SDK 콜백(asyncio).

## 6. 집

**권고: 새 저장소 `cogito5170/autonomy`.**
- 일곱 저장소를 sha 로 고정해 의존한다.
- 아무도 이 저장소를 import 하지 않는다. 의존 그래프의 맨 위다.

| 후보 | 비용 |
|---|---|
| action | action 은 표준 라이브러리만 쓰고, Policy(MS)를 import 하지 않는다(`BASELINE.md:227`). SDK 는 MS · DC · guard · health 를 모두 import 한다 |
| MS | MS 는 Policy 다. 배포 묶음 · 훅 어댑터(남의 에이전트를 Guard 로 막는 길)는 Policy 의 일이 아니다. 훅 길은 MS 를 쓰지도 않는다(Guard · DC · Sensor 만) |
| **새 저장소** | 저장소가 하나 더 생긴다(고정 · 통합할 것이 는다). 사용자가 만들어야 한다(세션은 저장소를 만들지 않는다) |

시제품 `sdk_draft/` 는 S2 에서 그 저장소로 옮기고, 이 저장소에서는 지운다.

## 7. S2 지시 목록 (제안)

**순서**: S2-0 → (S2-1 · S2-7a 함께) → (S2-2 · S2-3 함께) → S2-7b → S2 마감

| # | 저장소 | 할 일 | 끝난 기준 |
|---|---|---|---|
| S2-0 | 사용자 | 저장소 `cogito5170/autonomy` 를 만든다(세션 하나) | 저장소가 있다 |
| S2-1 | MS | ① `Runtime(risky=)` 를 Guard 모형까지 넘긴다(`guard_shadow.py:62-66`).<br>② 모듈 전역 id 셈(`telemetry.py:17` · `runtime.py:47`)을 Runtime 마다로 바꾼다.<br>③ L0 Recorder 에 Runtime 시계를 넘긴다(`l0.py:46`) | Runtime 둘에 같은 입력을 주면 결정 id 가 서로 같고, 한 Runtime 이 다른 Runtime 의 셈을 바꾸지 않는다. `risky` 를 바꾸면 Guard D 판정이 바뀐다(시험). 기존 212 초록 |
| S2-2 | Telemetry | ① `tool.start` 에 `tool_use_id`(ref) 칸을 **더한다**(cc_jsonl · cc_stream).<br>② 실제 Claude Code 실행에서 `PostToolUse` 가 불릴 때 transcript 에 그 결과가 이미 있는지 잰다.<br>③ 늘려 읽기(`from_cc_jsonl(…, since=)`)를 볼 만한지 보고한다 | catalog 더하기 · 시험. 측정 보고(몇 번 중 몇 번 있었나) |
| S2-3 | Sensor | ① L0 사건 목록 → 엔진 → export 를 한 번에 주는 편의 함수.<br>② MS `run_state` 어댑터(`.read` · `.subjects` = export `read` · `subjects`) | `$run.agent` 사후조건이 어댑터로 VERIFIED · NOT_VERIFIED 를 낸다(시험) |
| S2-4 | DC | 필수 없음. 훅 길은 `execution_control` 을 그대로 쓴다 | — |
| S2-5 | guard · health | 필수 없음 | — |
| S2-7a | autonomy(SDK) | `sdk_draft/` 를 옮긴다. pyproject 에 일곱 sha 를 고정하고 extras 는 `sensor` 하나. 판본 목록 시험 · 예제 · README | `pip install git+…autonomy@<sha>` 로 깔고 예제 한 바퀴가 초록(옆 저장소 경로 없이). `versions()` 가 판본 목록과 같다. 변이 RED |
| S2-7b | autonomy(SDK) | 훅 판정 `judge` 를 실제로 잇는다: transcript → cc_jsonl → Sensor → DC `execution_control` → DCView → guard. Claude Code 명령 훅 설정 예와 Agent SDK 콜백 예를 둔다 | 기록해 둔 transcript 로 시험한다. 실패 차례 뒤에 위험 도구가 오면 enforce 에서 deny(D), 정상이면 `{}`. shadow 는 늘 `{}`. `"allow"` 는 내지 않는다 |

## 8. 이 저장소에서 한 것과 검증

- **새 것**(action 패키지 밖):
  - `sdk_draft/autonomy.py` · `sdk_draft/hooks.py`
  - `tests/test_sdk_draft.py`(12)
  - 변이 11 개
- **action 패키지 코드는 그대로다**(`git diff 2f4791e -- action/` 가 비어 있다).
- **시험**:
  - stage-3 옆 저장소를 두면 **80 OK**, 건너뜀 0.
  - 옆 저장소가 없으면 대조 · 시제품 시험 29 개를 까닭과 함께 건너뛴다.
- **변이 71/71 RED.** 시제품 변이 11 개는 옆 저장소를 환경 변수(`<이름>_REPO`)로 주고 돌렸다.
- 낡은 스크래치 사본 하나를 지웠다(Telemetry `70b4feb`, 세션 안에서 만든 것). 그것이 `test_l0map` 의 옛 대체 경로에 걸려 헛 빨강을 내고 있었다.
