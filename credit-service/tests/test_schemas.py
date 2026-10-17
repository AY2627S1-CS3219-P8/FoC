from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import AdminAdjustmentRequest, CreditAccountCreate


def test_account_create_normalizes_student_number() -> None:
    payload = CreditAccountCreate(
        user_id=uuid4(), nus_student_number=" a0123456x "
    )
    assert payload.nus_student_number == "A0123456X"


@pytest.mark.parametrize("student_number", ["", "A123", "B0123456X", "A01234567"])
def test_account_create_rejects_invalid_student_number(student_number: str) -> None:
    with pytest.raises(ValidationError):
        CreditAccountCreate(user_id=uuid4(), nus_student_number=student_number)


def test_adjustment_requires_nonzero_amount_and_reason() -> None:
    with pytest.raises(ValidationError):
        AdminAdjustmentRequest(amount=0, reason="valid reason")
    with pytest.raises(ValidationError):
        AdminAdjustmentRequest(amount=1, reason="   ")
