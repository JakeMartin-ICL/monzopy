# monzopy
A simple async python wrapper for the Monzo API, used primarily by the Monzo Home Assistant integration.

## Webhooks

`UserAccount` provides ownership-safe primitives for managing webhooks on a specific
Monzo account:

- `await user_account.register_webhook(account_id, url)` registers a webhook and
  returns a frozen `Webhook` containing its `id`, `account_id`, and `url`.
- `await user_account.list_account_webhooks(account_id)` returns every `Webhook`
  registered for that account.
- `await user_account.delete_webhook(webhook_id)` deletes a webhook by ID.

The existing `register_webhooks`, `list_webhooks`, and `unregister_webhooks`
methods remain available for compatibility. They operate across all known accounts;
`list_webhooks` continues to return webhook ID strings and supports optional hostname
filtering.
