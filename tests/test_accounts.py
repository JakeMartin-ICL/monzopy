"""Tests for account response validation."""

from unittest.mock import AsyncMock

import pytest

from monzopy import InvalidMonzoAPIResponseError
from monzopy.monzopy import UserAccount


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
