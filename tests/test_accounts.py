"""Tests for account response validation."""

from unittest.mock import AsyncMock

import pytest

from monzopy import InvalidMonzoAPIResponseError
from monzopy.monzopy import UserAccount


async def test_accounts_preserve_api_metadata() -> None:
    """Test account metadata, including multiple owners, is preserved."""
    owners = [
        {
            "preferred_first_name": "Jake",
            "preferred_name": "Jake Martin",
            "user_id": "user-1",
        },
        {
            "preferred_first_name": "Jane",
            "preferred_name": "Jane Martin",
            "user_id": "user-2",
        },
    ]
    raw_account = {
        "id": "account-1",
        "type": "uk_retail_joint",
        "description": "Joint account between user-1 and user-2",
        "currency": "GBP",
        "owners": owners,
    }
    balance = {"balance": 1234, "total_balance": 5678, "currency": "GBP"}
    account = UserAccount(AsyncMock(side_effect=[{"accounts": [raw_account]}, balance]))

    assert await account.accounts() == [
        {
            **raw_account,
            "name": "Joint Account",
            "balance": balance,
        }
    ]
    assert "name" not in raw_account


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_key", ["id", "type"])
async def test_accounts_preserve_full_malformed_api_response(
    missing_key: str,
) -> None:
    malformed_account = {"id": "account-1", "type": "uk_retail"}
    del malformed_account[missing_key]
    response = {"accounts": [malformed_account]}
    account = UserAccount(AsyncMock(return_value=response))

    with pytest.raises(InvalidMonzoAPIResponseError) as raised:
        await account.accounts()

    assert raised.value.response == response
    assert raised.value.missing_key == missing_key
