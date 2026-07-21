"""Regression tests for pot transfer response handling."""

from unittest.mock import AsyncMock

import pytest

from monzopy import InvalidMonzoAPIResponseError
from monzopy.monzopy import UserAccount


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["pot_deposit", "pot_withdraw"])
async def test_malformed_pot_transfer_response_raises_api_error(
    operation: str,
) -> None:
    account = UserAccount(AsyncMock(return_value={}))

    with pytest.raises(InvalidMonzoAPIResponseError) as raised:
        await getattr(account, operation)("account-1", "pot-1", 100)

    assert raised.value.response == {}
    assert raised.value.missing_key is None
