# monzopy
A simple async python wrapper for the Monzo API, used primarily by the Monzo Home Assistant integration.

## Transactions

`await user_account.annotate_transaction(transaction_id, metadata)` adds or updates
transaction metadata and returns the updated transaction. Set a value to an empty
string to delete that key. Updating the `notes` key also updates the transaction's
top-level notes property.

## Feed items

`await user_account.create_feed_item(account_id, title, image_url, ...)` creates a
basic item in an account's Monzo feed. It accepts optional body text, a URL to open
when tapped, and background, title, and body colours.

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
