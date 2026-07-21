"""API for Monzo."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn
from urllib.parse import urlparse

from aiohttp import ClientSession

API_URL_BASE = "https://api.monzo.com"


class AbstractMonzoApi(ABC):  # pylint: disable=too-few-public-methods
    """An abstract class for accessing the Monzo API."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize.

        Args:
            api_key: An API key.
            session: An optional aiohttp ClientSession.
        """
        self._session: ClientSession = session
        self.user_account = UserAccount(self._request)

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        base_url: str = API_URL_BASE,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a request."""
        headers = kwargs.get("headers")

        if headers is None:
            headers = {}
        else:
            headers = dict(headers)

        access_token = await self.async_get_access_token()
        headers["Authorization"] = f"Bearer {access_token}"

        async with self._session.request(
            method,
            f"{base_url}/{endpoint}",
            **kwargs,
            headers=headers,
        ) as resp:
            data = await resp.json(content_type=None)

        try:
            data_dict: dict[str, Any] = dict(data)
        except ValueError:
            raise InvalidMonzoAPIResponseError

        return data_dict


INVALID_ACCOUNT_TYPES = ["uk_monzo_flex_backing_loan", "uk_prepaid"]

CURRENT_ACCOUNT = "uk_retail"

ACCOUNT_NAMES = {
    CURRENT_ACCOUNT: "Current Account",
    "uk_retail_joint": "Joint Account",
    "uk_monzo_flex": "Flex",
    "uk_business": "Business Account",
    "uk_rewards": "Cashback",
}

TOKEN_EXPIRY_CODE = "unauthorized.bad_access_token.expired"
INSUFFICIENT_PERMISSIONS_CODE = "forbidden.insufficient_permissions"
AUTH_EXPIRY_CODES = [TOKEN_EXPIRY_CODE, INSUFFICIENT_PERMISSIONS_CODE]
CODE = "code"


@dataclass(frozen=True)
class Webhook:
    """A webhook registered with Monzo for an account."""

    id: str
    account_id: str
    url: str


class UserAccount:
    """Define an object representing a Monzo account holder."""

    def __init__(self, request: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        """Initialise the account."""
        self._request: Callable[..., Awaitable[dict[str, Any]]] = request
        self._account_ids: set[str] = set()
        self._webhook_ids: list[str] = []

    async def accounts(self) -> list[dict[str, Any]]:
        """List accounts and their balances."""
        result = []

        accounts = await self._get_accounts()
        for account in accounts:
            balance = await self._request(
                "get", "balance", params={"account_id": account["id"]}
            )

            result.append(
                {
                    "id": account["id"],
                    "name": ACCOUNT_NAMES.get(account["type"], account["type"]),
                    "type": account["type"],
                    "balance": balance,
                }
            )

        return result

    async def pots(self) -> list[dict[str, Any]]:
        """List pots and their balance."""
        if not self._account_ids:
            await self._get_accounts()
        valid_pots = []
        for account_id in self._account_ids:
            pots = await self._request(
                "get", "pots", params={"current_account_id": account_id}
            )
            try:
                valid_pots += [pot for pot in pots["pots"] if pot["deleted"] is False]
            except KeyError as e:
                _raise_auth_or_response_error(pots, e.args[0] if e.args else None)
        return valid_pots

    async def _get_accounts(self) -> list[dict[str, Any]]:
        res = await self._request("get", "accounts")
        valid_accounts = []
        try:
            for acc in res["accounts"]:
                if acc["type"] not in INVALID_ACCOUNT_TYPES:
                    self._account_ids.add(acc["id"])
                    valid_accounts.append(acc)
        except KeyError as e:
            _raise_auth_or_response_error(res, e.args[0] if e.args else None)
        return valid_accounts

    async def pot_deposit(self, account_id: str, pot_id: str, amount: int) -> bool:
        """Deposit money into a pot from the specified account."""
        res = await self._request(
            "put",
            f"pots/{pot_id}/deposit",
            data={
                "source_account_id": account_id,
                "amount": amount,
                "dedupe_id": datetime.now(),
            },
        )
        if "id" not in res:
            _raise_auth_or_response_error(res)
        else:
            return True

    async def pot_withdraw(self, account_id: str, pot_id: str, amount: int) -> bool:
        """Withdraw money from a pot to a specified account."""
        res = await self._request(
            "put",
            f"pots/{pot_id}/withdraw",
            data={
                "destination_account_id": account_id,
                "amount": amount,
                "dedupe_id": datetime.now(),
            },
        )
        if "id" not in res:
            _raise_auth_or_response_error(res)
        else:
            return True

    async def register_webhook(self, account_id: str, url: str) -> Webhook:
        """Register a webhook for a single account."""
        response = await self._request(
            "post", "webhooks", data={"account_id": account_id, "url": url}
        )
        if "webhook" not in response or not isinstance(response["webhook"], dict):
            _raise_auth_or_response_error(response, "webhook")
        return _parse_webhook(response["webhook"], response)

    async def list_account_webhooks(self, account_id: str) -> list[Webhook]:
        """List all webhooks registered for a single account."""
        response = await self._request(
            "get", "webhooks", params={"account_id": account_id}
        )
        if "webhooks" not in response or not isinstance(response["webhooks"], list):
            _raise_auth_or_response_error(response, "webhooks")

        webhooks = []
        for webhook in response["webhooks"]:
            if not isinstance(webhook, dict):
                _raise_auth_or_response_error(response, "webhooks")
            webhooks.append(_parse_webhook(webhook, response))
        return webhooks

    async def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook by ID."""
        response = await self._request("delete", f"webhooks/{webhook_id}")
        if response:
            _raise_auth_or_response_error(response)

    async def register_webhooks(self, webhook_url: str) -> None:
        """Register webhooks for all bank accounts."""
        if not self._account_ids:
            await self._get_accounts()
        for account_id in self._account_ids:
            webhook = await self.register_webhook(account_id, webhook_url)
            self._webhook_ids.append(webhook.id)

    async def list_webhooks(self, host: str | None = None) -> list[str]:
        """List all webhooks registered on the account, optionally filtering by host."""
        hostname = urlparse(host).hostname if host else None
        if not self._account_ids:
            await self._get_accounts()
        webhook_ids = []
        for account_id in self._account_ids:
            for webhook in await self.list_account_webhooks(account_id):
                if not hostname or hostname == urlparse(webhook.url).hostname:
                    webhook_ids.append(webhook.id)
        return webhook_ids

    async def unregister_webhooks(self, host: str | None = None) -> None:
        """Unregister all webhooks, optionally filtering by host."""
        for webhook_id in await self.list_webhooks(host):
            await self.delete_webhook(webhook_id)


def _parse_webhook(webhook: dict[str, Any], response: dict[str, Any]) -> Webhook:
    """Parse and validate a webhook returned by Monzo."""
    values = {}
    for field in ("id", "account_id", "url"):
        if field not in webhook or not isinstance(webhook[field], str):
            _raise_auth_or_response_error(response, field)
        values[field] = webhook[field]
    return Webhook(**values)


def _authorisation_expired(response: dict[str, Any]) -> bool:
    return CODE in response and response[CODE] in AUTH_EXPIRY_CODES


def _raise_auth_or_response_error(
    response: dict[str, Any], missing_key: str | None = None
) -> NoReturn:
    if _authorisation_expired(response):
        raise AuthorisationExpiredError
    raise InvalidMonzoAPIResponseError(response, missing_key)


class InvalidMonzoAPIResponseError(Exception):
    """Error thrown when the external Monzo API returns an invalid response."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        missing_key: str | None = None,
    ) -> None:
        """Initialise error."""
        super().__init__()
        self.response = response
        self.missing_key = missing_key


class AuthorisationExpiredError(Exception):
    """Error thrown when the external Monzo API authentication has expired."""

    def __init__(self, *args: object) -> None:
        """Initialise error."""
        super().__init__(*args)
