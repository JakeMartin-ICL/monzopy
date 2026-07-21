"""Tests for account-scoped and backwards-compatible webhook operations."""

from unittest.mock import AsyncMock, call

import pytest

from monzopy import (
    AuthorisationExpiredError,
    InvalidMonzoAPIResponseError,
    Webhook,
)
from monzopy.monzopy import TOKEN_EXPIRY_CODE, UserAccount

WEBHOOK = {
    "id": "webhook-1",
    "account_id": "account-1",
    "url": "https://example.com/monzo",
}
AUTH_ERROR = {"code": TOKEN_EXPIRY_CODE}


@pytest.mark.asyncio
async def test_register_webhook_returns_typed_webhook_and_uses_exact_request() -> None:
    request = AsyncMock(return_value={"webhook": WEBHOOK})
    account = UserAccount(request)

    result = await account.register_webhook("account-1", "https://example.com/monzo")

    assert result == Webhook(**WEBHOOK)
    request.assert_awaited_once_with(
        "post",
        "webhooks",
        data={
            "account_id": "account-1",
            "url": "https://example.com/monzo",
        },
    )


@pytest.mark.asyncio
async def test_list_account_webhooks_returns_typed_webhooks() -> None:
    second = {
        "id": "webhook-2",
        "account_id": "account-1",
        "url": "https://other.example/monzo",
    }
    request = AsyncMock(return_value={"webhooks": [WEBHOOK, second]})
    account = UserAccount(request)

    result = await account.list_account_webhooks("account-1")

    assert result == [Webhook(**WEBHOOK), Webhook(**second)]
    request.assert_awaited_once_with(
        "get", "webhooks", params={"account_id": "account-1"}
    )


@pytest.mark.asyncio
async def test_delete_webhook_accepts_empty_object_response() -> None:
    request = AsyncMock(return_value={})
    account = UserAccount(request)

    await account.delete_webhook("webhook-1")
    request.assert_awaited_once_with("delete", "webhooks/webhook-1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "args"),
    [
        ("register_webhook", ("account-1", "https://example.com/monzo")),
        ("list_account_webhooks", ("account-1",)),
        ("delete_webhook", ("webhook-1",)),
    ],
)
async def test_webhook_operations_raise_for_authentication_failure(
    operation: str, args: tuple[str, ...]
) -> None:
    account = UserAccount(AsyncMock(return_value=AUTH_ERROR))

    with pytest.raises(AuthorisationExpiredError):
        await getattr(account, operation)(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "missing_key"),
    [
        ({}, "webhook"),
        ({"webhook": {}}, "id"),
        ({"webhook": {"id": "webhook-1"}}, "account_id"),
        (
            {
                "webhook": {
                    "id": "webhook-1",
                    "account_id": "account-1",
                }
            },
            "url",
        ),
    ],
)
async def test_register_webhook_rejects_missing_fields(
    response: dict[str, object], missing_key: str
) -> None:
    account = UserAccount(AsyncMock(return_value=response))

    with pytest.raises(InvalidMonzoAPIResponseError) as raised:
        await account.register_webhook("account-1", "https://example.com/monzo")

    assert raised.value.response == response
    assert raised.value.missing_key == missing_key


@pytest.mark.asyncio
async def test_list_account_webhooks_rejects_missing_webhooks_field() -> None:
    account = UserAccount(AsyncMock(return_value={}))

    with pytest.raises(InvalidMonzoAPIResponseError) as raised:
        await account.list_account_webhooks("account-1")

    assert raised.value.missing_key == "webhooks"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["id", "account_id", "url"])
@pytest.mark.parametrize("invalid_value", [None, 1, [], {}])
async def test_webhook_fields_must_be_strings(
    field: str, invalid_value: object
) -> None:
    malformed: dict[str, object] = dict(WEBHOOK)
    malformed[field] = invalid_value
    response = {"webhook": malformed}
    account = UserAccount(AsyncMock(return_value=response))

    with pytest.raises(InvalidMonzoAPIResponseError) as raised:
        await account.register_webhook("account-1", "https://example.com/monzo")

    assert raised.value.response == response
    assert raised.value.missing_key == field


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"webhook": None},
        {"webhook": []},
        {"webhooks": None},
        {"webhooks": {}},
        {"webhooks": [None]},
    ],
)
async def test_webhook_containers_must_have_correct_types(
    response: dict[str, object],
) -> None:
    account = UserAccount(AsyncMock(return_value=response))

    with pytest.raises(InvalidMonzoAPIResponseError):
        if "webhook" in response:
            await account.register_webhook("account-1", "https://example.com/monzo")
        else:
            await account.list_account_webhooks("account-1")


@pytest.mark.asyncio
async def test_register_webhooks_registers_once_for_every_known_account() -> None:
    async def request(
        method: str, endpoint: str, **kwargs: object
    ) -> dict[str, object]:
        if endpoint == "accounts":
            return {
                "accounts": [
                    {"id": "account-1", "type": "uk_retail"},
                    {"id": "account-2", "type": "uk_retail_joint"},
                ]
            }
        account_id = kwargs["data"]["account_id"]  # type: ignore[index]
        return {
            "webhook": {
                "id": f"webhook-{account_id}",
                "account_id": account_id,
                "url": "https://example.com/monzo",
            }
        }

    mocked_request = AsyncMock(side_effect=request)
    account = UserAccount(mocked_request)

    await account.register_webhooks("https://example.com/monzo")

    mocked_request.assert_has_awaits(
        [
            call("get", "accounts"),
            call(
                "post",
                "webhooks",
                data={
                    "account_id": "account-1",
                    "url": "https://example.com/monzo",
                },
            ),
            call(
                "post",
                "webhooks",
                data={
                    "account_id": "account-2",
                    "url": "https://example.com/monzo",
                },
            ),
        ],
        any_order=True,
    )
    assert mocked_request.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["https://example.com/callback", "example.com"])
async def test_list_webhooks_preserves_hostname_filtering(host: str) -> None:
    request = AsyncMock(
        return_value={
            "webhooks": [
                WEBHOOK,
                {
                    "id": "webhook-2",
                    "account_id": "account-1",
                    "url": "https://other.example/monzo",
                },
            ]
        }
    )
    account = UserAccount(request)
    account._account_ids.add("account-1")

    assert await account.list_webhooks(host) == ["webhook-1"]


@pytest.mark.asyncio
async def test_unregister_webhooks_deletes_every_listed_webhook() -> None:
    request = AsyncMock(
        side_effect=[
            {
                "webhooks": [
                    WEBHOOK,
                    {
                        "id": "webhook-2",
                        "account_id": "account-1",
                        "url": "https://other.example/monzo",
                    },
                ]
            },
            {},
            {},
        ]
    )
    account = UserAccount(request)
    account._account_ids.add("account-1")

    await account.unregister_webhooks()

    assert request.await_args_list == [
        call("get", "webhooks", params={"account_id": "account-1"}),
        call("delete", "webhooks/webhook-1"),
        call("delete", "webhooks/webhook-2"),
    ]


@pytest.mark.asyncio
async def test_unregister_webhooks_with_raw_hostname_deletes_only_matches() -> None:
    request = AsyncMock(
        side_effect=[
            {
                "webhooks": [
                    WEBHOOK,
                    {
                        "id": "webhook-2",
                        "account_id": "account-1",
                        "url": "https://other.example/monzo",
                    },
                ]
            },
            {},
        ]
    )
    account = UserAccount(request)
    account._account_ids.add("account-1")

    await account.unregister_webhooks("example.com")

    assert request.await_args_list == [
        call("get", "webhooks", params={"account_id": "account-1"}),
        call("delete", "webhooks/webhook-1"),
    ]
