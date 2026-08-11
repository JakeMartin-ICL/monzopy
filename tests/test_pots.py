"""Regression tests for pot transfer response handling."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from monzopy import InvalidMonzoAPIResponseError
from monzopy.monzopy import UserAccount


async def test_pots_include_owning_account() -> None:
    """Test pots retain the current account used to retrieve them."""

    async def request(method: str, endpoint: str, **kwargs: Any) -> dict[str, object]:
        if endpoint == "accounts":
            return {
                "accounts": [
                    {"id": "account-1", "type": "uk_retail"},
                    {"id": "account-2", "type": "uk_retail_joint"},
                ]
            }

        account_id = kwargs["params"]["current_account_id"]
        return {
            "pots": [
                {
                    "id": f"pot-{account_id}",
                    "deleted": False,
                }
            ]
        }

    pots = await UserAccount(request).pots()

    assert sorted(pots, key=lambda pot: pot["id"]) == [
        {
            "id": "pot-account-1",
            "deleted": False,
            "current_account_id": "account-1",
        },
        {
            "id": "pot-account-2",
            "deleted": False,
            "current_account_id": "account-2",
        },
    ]


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
