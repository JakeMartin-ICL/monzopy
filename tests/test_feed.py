"""Tests for feed item operations."""

from unittest.mock import AsyncMock

import pytest

from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError
from monzopy.monzopy import TOKEN_EXPIRY_CODE, UserAccount


async def test_create_feed_item_uses_exact_request() -> None:
    """Test a basic feed item is encoded using Monzo's form field names."""
    request = AsyncMock(return_value={})
    account = UserAccount(request)

    await account.create_feed_item(
        "account-1",
        "My custom item",
        "https://example.com/image.png",
        body="Some body text to display",
        url="https://example.com/details",
        background_color="#FCF1EE",
        title_color="#333333",
        body_color="#FCF1EE",
    )

    request.assert_awaited_once_with(
        "post",
        "feed",
        data={
            "account_id": "account-1",
            "type": "basic",
            "params[title]": "My custom item",
            "params[image_url]": "https://example.com/image.png",
            "params[body]": "Some body text to display",
            "url": "https://example.com/details",
            "params[background_color]": "#FCF1EE",
            "params[title_color]": "#333333",
            "params[body_color]": "#FCF1EE",
        },
    )


async def test_create_feed_item_omits_optional_fields() -> None:
    """Test optional feed item fields are not sent when omitted."""
    request = AsyncMock(return_value={})
    account = UserAccount(request)

    await account.create_feed_item(
        "account-1", "My custom item", "https://example.com/image.png"
    )

    request.assert_awaited_once_with(
        "post",
        "feed",
        data={
            "account_id": "account-1",
            "type": "basic",
            "params[title]": "My custom item",
            "params[image_url]": "https://example.com/image.png",
        },
    )


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        ({"unexpected": "value"}, InvalidMonzoAPIResponseError),
        ({"code": TOKEN_EXPIRY_CODE}, AuthorisationExpiredError),
    ],
)
async def test_create_feed_item_rejects_error_responses(
    response: dict[str, str], exception: type[Exception]
) -> None:
    """Test non-empty feed responses are treated as errors."""
    account = UserAccount(AsyncMock(return_value=response))

    with pytest.raises(exception):
        await account.create_feed_item(
            "account-1", "My custom item", "https://example.com/image.png"
        )
