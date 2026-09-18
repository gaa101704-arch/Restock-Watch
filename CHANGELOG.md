# Changelog

All notable changes to Restock Watch are documented here.

The project follows [Semantic Versioning](https://semver.org/) for public releases.

## [Unreleased]

### Added
- Importable n8n-native monitoring workflow for n8n Cloud and self-hosted n8n.
- Importable n8n webhook bridge for Python watcher integrations.
- n8n deployment and security documentation.
- Python package metadata and the `restock-watch` console command.
- GitHub Actions CI across Python 3.11, 3.12, and 3.13.
- Contribution and security policies.
- Regression tests for parser scoping, state restoration, and notification delivery failures.

### Changed
- JSON-LD availability is parsed structurally before regex fallback.
- Explicit product matching fails closed rather than using another product's availability.
- Schema.org `LimitedAvailability` and `MadeToOrder` are treated as orderable.
- Source adapter output is validated before transition detection.
- Conflicting observations for one target are treated as unknown.
- Dry runs restore in-memory state after evaluating transitions.

### Fixed
- Restock state no longer advances when every notification channel fails, allowing the alert to retry on the next cycle.

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
