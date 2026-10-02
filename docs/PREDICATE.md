# PREDICATE — 술어 · 인자 검사 한 벌 (CMD-A4 · BD-108)

코드: [`action/predicate.py`](../action/predicate.py) · [`action/params.py`](../action/params.py).
원본은 MS 다(stage-2 `2cb7e61`):
- 술어: `ms/predicate.py`
- 인자 검사: `ms/tools.py:49-65` 의 `ToolSpec.check_args` + `ms/model.py:78-107` 의 `PropertySpec.validate`

같은 언어가 지금 세 벌 더 있다. MS 는 원본이고, 나머지 둘은 이렇다.
- guard: `guard/predicate.py` · `guard/params.py`. GUARD.md F1 이 이 중복을 적어 두었다.
- health: `health/predicate.py`.

이 한 벌로 옮기는 일은 각 저장소의 다음 지시(G-next · M-next · H-next)다. 아래 차이가 그때 고칠 것이다.

## 1. 다른 점

| | 이 한 벌 | MS | guard | health | 옮길 때 |
|---|---|---|---|---|---|
| `check` 기본 | MS 와 같다(글까지) | — | 받느냐만 같다 | — | 그대로 |
| 속성 참조 `{"prop","mul"}` | 받는다. `check(p, refs=False)` 이면 거절 | 받는다 | 받는다 | **거절**(verification-record/1) | health 는 `check(p, refs=False, named=True)` |
| 첫 칸(속성 이름) 검사 | 기본은 안 본다. `named=True` 면 빈 것 아닌 문자열 | 안 본다 | 안 본다 | **본다** | health 는 `named=True`. ActionSpec 은 사전 · 사후조건 모두 `named=True` 로 부른다 |
| `props_of` | 처음 나온 순서의 **목록** | **집합** | 목록 | 없다 | MS 는 `set(props_of(…))`. `ms/model.py:154` 가 `|=` 로 쓴다 |
| `all_hold` | 있다 | 있다 | 없다 | 없다 | — |
| 인자: 모르는 타입 | **문제로 적는다** | 그냥 통과 | 문제로 적는다 | — | 명세(`action-spec/1`)를 지난 params 에서는 같다. ActionSpec 이 지을 때 타입을 거르기 때문이다 |
| 인자: `type` 이 없음 | number 로 읽는다 | 같다 | 같다 | — | 그대로 |

**바뀌지 않는 뜻**:
- 값이 없거나, 걸린 속성이 없거나, 견줄 수 없으면 거짓이다. 모르는 것을 참으로 세지 않는다.
- `exists` · `missing` 만 값이 없음을 묻는다.
- 정수 자리의 `2.0` 은 `2` 로 읽는다. 참거짓은 수가 아니다.

## 2. 같다는 증거

**대조 시험** `tests/test_predicate.py`. 옆 저장소를 두면 건너뜀이 0 이다.

| 대상 | 무엇을 견주나 |
|---|---|
| MS | 술어 25 개 × 값 3 벌의 `holds`. 술어 39 개의 `check` 문제 목록이 **글까지** 같다. `props_of` 는 집합으로 같다. `all_hold` |
| MS | 인자: params 7 × args 22 의 `check_args` 문제 목록이 **글까지** 같다 |
| guard | `holds` · `check`(받느냐) · `props_of`(순서까지). 인자는 모르는 타입을 넣은 8 × 22 로 견준다 |
| guard | 자기 술어 시험 파일(`tests/test_predicate.py`)이 import 한 줄만 바꿔 **그대로 지난다** |
| health | 속성 참조 없는 술어의 `holds`. `check(refs=False, named=True)` 가 health 의 `check` 와 받느냐가 같다 |
| health | 자기 술어 시험 파일이 얇은 덧씌움(위 모드)으로 **그대로 지난다**. 그 파일 안의 MS 대조 시험도 함께 돈다 |

**바꿔 끼우기 탐침** [`eval/predicate_swap.py`](../eval/predicate_swap.py).
- 하는 일: 세 저장소의 **복사본**에서 자기 술어 · 인자 모듈을 이 한 벌을 다시 내보내는 얇은 모듈로 바꾼다. 그리고 시험 **전체**를 돌린다.
- 옆 저장소는 stage-2 이고, Sensor 까지 두었다.

| 저장소 | 결과 |
|---|---|
| MS | 185 OK, 건너뜀 0 |
| guard | 81 OK, 건너뜀 0 |
| health | 26 OK, 건너뜀 0 |

얇은 모듈이 하는 일이 곧 §1 의 "옮길 때" 칸이다:
- MS: `props_of` 를 `set` 으로 감싸고, `ToolSpec.check_args` 가 `action.params.check_args` 를 부른다.
- guard: 그대로 다시 내보낸다.
- health: `check(refs=False, named=True)`.
