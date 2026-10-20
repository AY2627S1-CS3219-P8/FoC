from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import AdminAdjustmentRequest, CreditAccountCreate


def test_account_create_accepts_empty_or_uuid_only_payload() -> None:
    assert CreditAccountCreate().user_id is None
    user_id = uuid4()
    assert CreditAccountCreate(user_id=user_id).user_id == user_id


def test_account_create_rejects_unrelated_identity_fields() -> None:
    with pytest.raises(ValidationError):
        CreditAccountCreate(nus_student_number="A0123456X")


def test_adjustment_requires_nonzero_amount_and_reason() -> None:
    with pytest.raises(ValidationError):
        AdminAdjustmentRequest(amount=0, reason="valid reason")
    with pytest.raises(ValidationError):
        AdminAdjustmentRequest(amount=1, reason="   ")
