# n8n deployment

Restock Watch ships with importable n8n workflows for both n8n Cloud and self-hosted n8n.

There are two supported patterns.

## Option 1: n8n-native monitor

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

Workflow static data is appropriate for a small state value like a last-seen status, but it is not intended to become a general database.

## Option 2: Python watcher + n8n routing

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

In n8n, create a workflow and choose **Import from File**, then select the JSON file from the `n8n/` directory. Review every node before activation.
