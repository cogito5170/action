"""Action -- L5 EXECUTE 의 꼴(계약). BD-25 · BD-95.

꼴: ActionIntent · ActionCommand · ActionOutcome (action-contract/1, BD-96) · ActionSpec · ActionModel (action-spec/1 · action-model/1, BD-108).
한 벌: 술어(predicate) · 인자 검사(params). 실행기: executor (shadow · execute). docs/CONTRACT.md · docs/EXECUTOR.md · docs/PREDICATE.md
"""
from . import l0map
from .canonical import canonical_json, check_json, digest
from .forms import (AUTHOR_KINDS, FORMS, SPEC, ActionCommand, ActionIntent, ActionOutcome, ContractError)
from .spec import MODEL_SCHEMA, SPEC_SCHEMA, ActionModel, ActionSpec

__all__ = ["AUTHOR_KINDS", "FORMS", "SPEC", "ActionCommand", "ActionIntent", "ActionOutcome", "ContractError",
           "MODEL_SCHEMA", "SPEC_SCHEMA", "ActionModel", "ActionSpec", "canonical_json", "check_json", "digest", "l0map"]
