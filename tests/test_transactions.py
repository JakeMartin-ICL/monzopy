"""Tests for transaction operations."""

from unittest.mock import AsyncMock

import pytest

from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError
from monzopy.monzopy import TOKEN_EXPIRY_CODE, UserAccount

TRANSACTION = {
    "id": "transaction-1",
    "metadata": {"project": "home-assistant"},
    "notes": "Updated note",
}


async def test_annotate_transaction_returns_updated_transaction() -> None:
    """Test metadata is encoded using Monzo's form field names."""
    request = AsyncMock(return_value={"transaction": TRANSACTION})
    account = UserAccount(request)

    result = await account.annotate_transaction(
        "transaction-1",
        {
            "project": "home-assistant",
            "obsolete": "",
            "notes": "Updated note",
        },
    )

    assert result == TRANSACTION
    request.assert_awaited_once_with(
        "patch",
        "transactions/transaction-1",
        data={
            "metadata[project]": "home-assistant",
            "metadata[obsolete]": "",
            "metadata[notes]": "Updated note",
        },
    )


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        ({}, InvalidMonzoAPIResponseError),
        ({"transaction": None}, InvalidMonzoAPIResponseError),
        ({"code": TOKEN_EXPIRY_CODE}, AuthorisationExpiredError),
    ],
)
async def test_annotate_transaction_rejects_error_responses(
    response: dict[str, object], exception: type[Exception]
) -> None:
    """Test malformed and authentication error responses are rejected."""
    account = UserAccount(AsyncMock(return_value=response))

    with pytest.raises(exception):
        await account.annotate_transaction("transaction-1", {"notes": "Updated"})
