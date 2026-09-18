# restock-watch

[![CI](https://github.com/gaa101704-arch/Restock-Watch/actions/workflows/ci.yml/badge.svg)](https://github.com/gaa101704-arch/Restock-Watch/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Watch product pages and get told **once** when something you want becomes
buyable.

Built for console launches and GPU drops, but it works for anything with a
product page. It runs on one machine, needs no server, no database and no
account anywhere, and the core has **zero dependencies** beyond Python 3.11.

```
$ python3 -m restock_watch
2026-09-17 19:05:59 INFO    Nintendo: OUT_OF_STOCK (unchanged)
2026-09-17 19:05:59 INFO    nis:Best Buy: OUT_OF_STOCK -> PREORDER

*** IN STOCK: Nintendo Switch 2 - Zelda 40th Anniversary Edition ***
Nintendo Switch 2 - Zelda 40th Anniversary Edition is available:

  nis:Best Buy: OUT_OF_STOCK -> PREORDER

Buy links:
  https://www.nintendo.com/us/store/products/...
```

## What it does, and what it deliberately does not

It polls the pages you list, normalises whatever they say into a small set
of statuses, and when one crosses from "can't buy" to `IN_STOCK` or
`PREORDER` it notifies you on every channel you enabled. It remembers what
it last saw, so a restock pages you once, not every five minutes until you
notice.

It **does not buy anything for you.** There is no cart code, no checkout
automation, no stored payment details. It tells you; you decide. That is a
deliberate limit, not a missing feature.

## Quick start

Needs Python 3.11 or newer. The default watcher has no runtime dependencies outside the standard library.

```bash
git clone https://github.com/gaa101704-arch/Restock-Watch.git restock-watch
cd restock-watch

cp config.example.toml config.toml
$EDITOR config.toml          # point it at what you actually want

python3 -m restock_watch     # one cycle, prints to the terminal
```

If you prefer an installed CLI:

```bash
python3 -m pip install -e .
restock-watch --config config.toml
```

The first run records a baseline and stays quiet — it is not going to alert
you about a status you already knew. From the second run on, it reports
changes.

Then pick how it should keep running:

```bash
python3 -m restock_watch --loop      # stays in the foreground
```

or install the systemd user timer / cron line in [`deploy/`](deploy/), which
is what you want if it should survive you closing the laptop.

## n8n (optional, and best alongside the watcher)

If you already run **n8n Cloud** or **self-hosted n8n**, there is importable
workflow JSON for it. n8n is entirely optional — everything above works
without it — and it is at its best *next to* the Python watcher rather than
instead of it:

- [`n8n/restock-watch-webhook.json`](n8n/restock-watch-webhook.json) — **the
  recommended pairing.** The watcher keeps doing the monitoring, where it has
  the browser source, per-retailer adapters and the transition logic; n8n
  takes the alert from there and handles Slack, Telegram, email, logging,
  escalation and anything else downstream. Set
  `[notify.webhook] enabled = true` and point `RESTOCK_WEBHOOK_URL` at it.
- [`n8n/restock-watch-native.json`](n8n/restock-watch-native.json) — a
  lightweight HTTP/JSON-LD monitor that runs entirely inside n8n, for when you
  would rather not run a Python process at all. It cannot drive a browser and
  has no custom adapters, so treat it as the smaller option, not the better
  one.

The workflow templates contain no credential IDs, tokens, or secrets. Import
one, replace the example configuration, attach your credentials or delivery
nodes, test it, and activate it.

See [docs/N8N.md](docs/N8N.md) for setup details and the tradeoffs.

## Getting alerts somewhere other than the terminal

Enable a channel in `config.toml` and put its credentials in the
environment — never in the config file:

```bash
cp .env.example .env
$EDITOR .env
set -a; . ./.env; set +a
python3 -m restock_watch --test-notify
```

| Channel | Enable with | Needs |
|---|---|---|
| `console` | on by default | nothing |
| `telegram` | `[notify.telegram] enabled = true` | bot token + chat id (~2 min, see `.env.example`) |
| `email` | `[notify.email] enabled = true` | SMTP host + app password |
| `webhook` | `[notify.webhook] enabled = true` | a URL — point it at ntfy, Home Assistant, n8n, Discord, whatever |

Enable several. They fire independently, so a dead SMTP server does not
cost you the Telegram message.

## Choosing what to watch

Each `[[watch]]` in the config picks a **source** — a small adapter that
knows how to read one kind of page:

| Source | How it works | Good for |
|---|---|---|
| `jsonld` | Reads schema.org availability out of the served HTML | Most first-party stores. Fast, no dependencies. |
| `nowinstock` | Scrapes a NowInStock tracker table | Several retailers from one request |
| `browser` | Headless Chromium, inspects the real buy box | Stores that render in JavaScript or block plain HTTP |

`browser` is the only one with a dependency, and it is optional:

```bash
pip install playwright
python3 -m playwright install chromium
```

Adding a source for a store none of these handle is about thirty lines —
see [`docs/ADDING-A-SOURCE.md`](docs/ADDING-A-SOURCE.md).

## Please don't hammer the retailers

The minimum interval is 60 seconds and the default is 300, and you should
leave it there or raise it. Polling a storefront every few seconds from a
home connection gets your IP rate-limited or blocked, which makes you
*slower* to hear about a restock, not faster. It also degrades a service
other people are using. Check the site's terms; some prohibit automated
access outright, and a published API is always the better path when one
exists.

Two watches at five minutes covering four retailers each will beat one
aggressive scraper that got itself banned.

## How the alerting logic works

Everything is compared against a normalised vocabulary:
`IN_STOCK`, `PREORDER`, `BACKORDER`, `OUT_OF_STOCK`, plus `UNKNOWN` and
`BLOCKED` for "we learned nothing this cycle".

The rules that matter:

- Only a transition **into** `IN_STOCK` or `PREORDER` alerts. Pre-orders count
  on purpose: for a console launch the pre-order window is usually the only
  shot at a launch-day unit, and it can open and sell out without the item ever
  being "in stock".
- `UNKNOWN` and `BLOCKED` never alert and never overwrite a known status —
  so a CAPTCHA on Tuesday followed by a normal page on Wednesday does not
  look like a restock.
- First sighting of a target is a baseline, not an alert.
- A source that throws or returns nothing is a failure, not an
  out-of-stock. Silence is never treated as bad news.

Set `alert_on_any_change = true` while you are tuning if you want to see
every transition, including things going out of stock.

Exit codes, for wrapping in a monitor: `0` idle, `2` an alert fired,
`3` an alert was due but no channel delivered it (state is left untouched so
the next cycle retries), `42` bad config.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Layout

```text
restock_watch/
  __main__.py     CLI
  watcher.py      poll -> detect transition -> alert
  status.py       the status vocabulary and normalisation
  state.py        last-seen statuses, atomic JSON
  config.py       TOML loading and validation
  sources/        one adapter per kind of page
  notify/         one module per channel
n8n/              importable n8n Cloud / self-hosted workflows
deploy/           systemd user timer + cron example
docs/             integration and extension guides
tests/            unit tests for parsing, state and alerting logic
.github/workflows CI
```

## Contributing and security

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the
development workflow and source-adapter rules.

Please report security-sensitive issues privately rather than opening a public
issue. See [SECURITY.md](SECURITY.md). Release history is tracked in
[CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
