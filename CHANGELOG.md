# Changelog

All notable changes to Restock Watch are documented here.

The project follows [Semantic Versioning](https://semver.org/) for public releases.

## [Unreleased]

### Added
- Importable n8n-native monitoring workflow for n8n Cloud and self-hosted n8n.
- Importable n8n webhook bridge for Python watcher integrations.
- n8n deployment and security documentation, framing n8n as optional and
  documenting the webhook bridge as the recommended pairing.
- Python package metadata and the `restock-watch` console command.
- GitHub Actions CI across Python 3.11, 3.12, and 3.13.
- Contribution and security policies.
- Regression tests for parser scoping, state restoration, and notification delivery failures.
- Parser fixtures captured from the live Nintendo and NowInStock pages, replacing hand-written ones whose markup the sites never actually served.

### Changed
- JSON-LD availability is parsed structurally before regex fallback.
- Explicit product matching fails closed rather than using another product's availability.
- The example config matches the Nintendo store's own SKU (`121642`) and the full NowInStock edition name, so neither the plain console nor the Mario Kart bundle can satisfy the match.
- Schema.org `LimitedAvailability` and `MadeToOrder` are treated as orderable.
- Source adapter output is validated before transition detection.
- Conflicting observations for one target are treated as unknown, except
  that UNKNOWN/BLOCKED readings carry no signal and never override a
  source that did observe a status.
- Dry runs restore in-memory state after evaluating transitions.

### Fixed
- NowInStock rows are read from the `stockStatus*` cell instead of the row's CSS class. Every row on the live tracker shares `class="offRow"` regardless of state, so a retailer showing `Preorder` was reported as out of stock and never alerted.
- Restock state no longer advances when every notification channel fails, allowing the alert to retry on the next cycle.
- A source returning UNKNOWN or BLOCKED no longer cancels out a working source reporting the same target, which could silently suppress a restock alert.
- A total notification-delivery failure now exits with the documented code `3` instead of raising an uncaught exception in one-shot (cron/systemd) mode.

## [1.0.0] - 2026-09-17

Initial release baseline.

### Added
- JSON-LD, NowInStock, and optional Playwright browser sources.
- Console, Telegram, SMTP email, and generic webhook notifications.
- Persistent atomic JSON state.
- Transition-aware alerting for `IN_STOCK` and `PREORDER`.
- systemd user timer and cron deployment examples.
- Unit tests for normalization, transitions, state persistence, alert rendering, and NowInStock parsing.
- MIT license.
