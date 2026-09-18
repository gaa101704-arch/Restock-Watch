# Release checklist

Use this checklist before publishing Restock Watch as a public release.

## Already automated

- [x] Python package metadata exists in `pyproject.toml`.
- [x] CI runs on Python 3.11, 3.12, and 3.13.
- [x] Unit tests cover state transitions, notification failure recovery, JSON-LD scoping, and dated live-derived HTML fixtures.
- [x] n8n Cloud/self-hosted workflow JSON is included without credentials or secrets.
- [x] Contribution, security, n8n deployment, and changelog documentation exists.
- [x] Draft PR #1 isolates the release-readiness changes from `main`.

## Repository settings requiring GitHub admin access

The GitHub integration used during review cannot modify these settings.

### About

Suggested description:

> Self-hosted Python restock and preorder monitor with transition-aware alerts, Playwright support, and importable n8n workflows.

Suggested topics:

`python`, `restock`, `inventory-monitor`, `stock-alerts`, `n8n`, `playwright`, `automation`, `self-hosted`

If the project is meant to be publicly discoverable, change repository visibility from private to public only after reviewing the full Git history for secrets.

### Main-branch protection

Recommended minimum:

- Require a pull request before merging.
- Require these status checks:
  - `test (3.11)`
  - `test (3.12)`
  - `test (3.13)`
- Require conversation resolution before merging.
- Block force pushes to `main`.
- Block deletion of `main`.
- Keep an administrator bypass path if this remains a single-maintainer repository.

Optional repository hygiene:

- Prefer squash merges for small focused contributions.
- Delete head branches after merge.

## n8n import validation

Before marking PR #1 ready:

1. Import `n8n/restock-watch-native.json` into a current n8n 2.x instance.
2. Confirm all nodes load without migration warnings.
3. Replace the example URL with a safe test page and run once manually.
4. Publish/activate the workflow and confirm a triggered production execution persists static state.
5. Confirm a second unchanged execution does not alert.
6. Change the test page/state to an actionable status and confirm exactly one alert is sent.
7. Import `n8n/restock-watch-webhook.json`.
8. Add authentication to the Webhook node.
9. POST a representative Restock Watch payload and confirm the workflow responds with `ok: true`.
10. Connect one real delivery node and verify credentials are referenced by n8n rather than embedded in exported JSON.

## Release

After PR #1 is reviewed, CI is green, and n8n import validation passes:

1. Merge PR #1 into `main`.
2. Confirm CI passes on `main`.
3. Update the `[Unreleased]` section in `CHANGELOG.md` to the intended release version/date if needed.
4. Create a Git tag matching the package version.
5. Create a GitHub Release using the changelog entry as release notes.
6. Only then advertise the repository as a stable public release.
