# n8n deployment

Restock Watch ships with importable n8n workflows for both n8n Cloud and self-hosted n8n.

n8n is **optional**. The Python watcher is self-contained and needs nothing
here. This page is for people who already run n8n and want the alerts to land
in an automation platform rather than only in a message.

There are two supported patterns, and they are not equal. If you run both
pieces, **Option 2 is the recommended shape**: the watcher does the
monitoring, n8n does the routing. Each is good at the part the other is not —
the watcher has the browser source, the per-retailer adapters and the
transition logic; n8n has the delivery nodes, retries, logging and escalation.
Option 1 exists for people who would rather not run a Python process at all,
and it gives up real capability to get there.

## Option 1: n8n-native monitor (the smaller option)

Import:

`n8n/restock-watch-native.json`

This workflow runs entirely inside n8n. It is intended for product pages whose availability can be read from ordinary HTML or JSON-LD without a real browser.

After import:

1. Open **Watch Configuration** and replace the example product name, URL, label, optional match string, and notification webhook URL.
2. Run the workflow manually once to confirm the page can be fetched and parsed.
3. Activate the workflow. Production executions persist the last known status in workflow static data.
4. Set the schedule you want. Five minutes is the default. Do not poll retailers aggressively.
5. Replace the generic notification webhook with Slack, Telegram, email, Discord, or another n8n node if preferred.

The first successful production observation establishes a baseline and does not alert. A later transition into `IN_STOCK` or `PREORDER` generates an alert.

### Limitations

The n8n-native workflow does not run Playwright and is intentionally narrower than the Python application. Use the webhook bridge when the target site requires a browser, custom source adapter, or retailer-specific parsing.

It also duplicates the availability logic in a second language, so parser fixes made in the Python source adapters do not reach it. Running both patterns against the same product is a reasonable belt-and-braces setup — two schedulers, two parsers, two failure modes — but keep the native workflow pointed at pages simple enough that plain HTML is genuinely enough.

Workflow static data is appropriate for a small state value like a last-seen status, but it is not intended to become a general database. n8n currently marks workflow static data as experimental: it is saved only after a successful published trigger/webhook execution, it is not persisted during manual test executions, and n8n cautions against high-frequency use. If you later expand this workflow into many products or richer history, move state into an n8n Data Table or an external database.

## Option 2: Python watcher + n8n routing (recommended)

Import:

`n8n/restock-watch-webhook.json`

Use this when the Python watcher should continue doing the monitoring and n8n should handle delivery, logging, escalation, or downstream automation.

In Restock Watch:

```toml
[notify.webhook]
enabled = true
```

Set:

```bash
RESTOCK_WEBHOOK_URL=https://YOUR_N8N_HOST/webhook/restock-watch
```

The Python watcher sends this payload:

```json
{
  "title": "IN STOCK: Example Product",
  "body": "Example Product is available...",
  "changes": [
    {
      "target": "Example Store",
      "from": "OUT_OF_STOCK",
      "to": "IN_STOCK",
      "actionable": true
    }
  ],
  "actionable": true
}
```

After importing the n8n workflow, connect your preferred delivery nodes after **Validated Alert**.

## Credentials and security

The workflow JSON files intentionally contain no real credentials or credential IDs.

For production:

- Add authentication to the inbound Webhook node before exposing it publicly.
- Prefer an n8n credential object over putting tokens directly into node fields.
- Use HTTPS.
- On self-hosted n8n, keep the encryption key stable and back up the n8n database.
- Do not add Execute Command solely to run Restock Watch. n8n Cloud does not provide that execution model, and modern self-hosted installations may restrict command execution by default.

## Importing

In n8n, open the workflow editor menu and choose **Import from File**, then select the JSON file from the `n8n/` directory. n8n also supports **Import from URL** if you point it at the raw GitHub JSON file. Review every node before activation.
