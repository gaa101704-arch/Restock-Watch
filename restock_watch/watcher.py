"""The polling loop: check every watch, detect transitions, alert once."""

from __future__ import annotations

import logging
from typing import Dict, List

from . import status as st
from .notify import Alert, dispatch
from .sources import get as get_source
from .state import State

LOG = logging.getLogger("restock-watch")


class NotificationDeliveryError(RuntimeError):
    """No enabled notification channel successfully delivered an alert."""


def collect(watches: List[dict]) -> Dict[str, str]:
    """Run every watch and merge the results into one {target: status} map.

    Invalid or conflicting source output is downgraded to UNKNOWN instead of
    being allowed to create a false transition.
    """
    observed: Dict[str, str] = {}
    conflicted: set[str] = set()

    for watch in watches:
        label = watch.get("label") or watch.get("source")
        try:
            result = get_source(watch["source"])(watch)
        except Exception as exc:
            # A source that throws is a source that told us nothing. Record
            # BLOCKED so the run is visible in the log, and move on.
            LOG.error("watch %s failed: %s", label, exc)
            observed[str(label)] = st.BLOCKED
            continue

        if not result:
            LOG.warning("watch %s returned nothing", label)

        for target, current in result.items():
            target = str(target)
            if current not in st.ALL:
                LOG.error(
                    "watch %s returned invalid status %r for %s; treating it as UNKNOWN",
                    label,
                    current,
                    target,
                )
                current = st.UNKNOWN

            if target in conflicted:
                continue

            previous = observed.get(target)
            if previous is None or previous == current:
                observed[target] = current
                continue

            # The readings differ, but UNKNOWN and BLOCKED are not opinions —
            # they mean "this source learned nothing". A bot-walled browser
            # check must not veto a working one, or the alert this tool exists
            # to deliver is silently dropped.
            if current in st.UNINFORMATIVE:
                LOG.info(
                    "watch %s reported %s for %s (no signal); keeping %s",
                    label,
                    current,
                    target,
                    previous,
                )
                continue

            if previous in st.UNINFORMATIVE:
                LOG.info(
                    "watch %s reported %s for %s, replacing the earlier %s (no signal)",
                    label,
                    current,
                    target,
                    previous,
                )
                observed[target] = current
                continue

            # Two sources both claim to know, and they disagree. Neither is
            # trustworthy this cycle.
            LOG.error(
                "target %s was reported with conflicting statuses %s and %s; "
                "treating this cycle as UNKNOWN",
                target,
                previous,
                current,
            )
            observed[target] = st.UNKNOWN
            conflicted.add(target)

    return observed


def detect_changes(observed: Dict[str, str], state: State) -> List[dict]:
    """Compare against last known status and update state in place.

    An uninformative reading (UNKNOWN/BLOCKED) never counts as a change and
    never overwrites a known status. Otherwise a CAPTCHA today plus a normal
    page tomorrow could look like a restock.
    """
    changes: List[dict] = []
    for target in sorted(observed):
        current = observed[target]
        previous = state.get(target)

        if current in st.UNINFORMATIVE:
            LOG.info("%s: %s (no signal, keeping %s)", target, current, previous or "nothing")
            continue

        if previous is None:
            # First sighting: record it as the baseline. Alerting here would
            # mean a fresh install pages you about a pre-order you already
            # knew about.
            LOG.info("%s: baseline %s", target, current)
            state.set(target, current)
            continue

        if previous == current:
            LOG.info("%s: %s (unchanged)", target, current)
            continue

        LOG.info("%s: %s -> %s", target, previous, current)
        changes.append(
            {
                "target": target,
                "from": previous,
                "to": current,
                "actionable": current in st.ACTIONABLE,
            }
        )
        state.set(target, current)

    return changes


def build_alert(changes: List[dict], config: dict) -> Alert:
    product = config.get("general", {}).get("product_name", "Tracked item")
    links = config.get("general", {}).get("links", [])
    actionable = [c for c in changes if c["actionable"]]

    if actionable:
        title_prefix = (
            "IN STOCK"
            if any(change["to"] == st.IN_STOCK for change in actionable)
            else "PREORDER"
        )
        title = f"{title_prefix}: {product}"
        lines = [f"{product} is available:", ""]
        lines += [f"  {c['target']}: {c['from']} -> {c['to']}" for c in actionable]
        other = [c for c in changes if not c["actionable"]]
        if other:
            lines += ["", "Also changed:"]
            lines += [f"  {c['target']}: {c['from']} -> {c['to']}" for c in other]
        if links:
            lines += ["", "Buy links:"] + [f"  {link}" for link in links]
    else:
        title = f"Status changed: {product}"
        lines = [f"{product} changed, but is not purchasable yet:", ""]
        lines += [f"  {c['target']}: {c['from']} -> {c['to']}" for c in changes]

    return Alert(
        title=title,
        body="\n".join(lines),
        changes=changes,
        actionable=bool(actionable),
    )


def _restore_state(state: State, statuses: dict, meta: dict) -> None:
    state.statuses = dict(statuses)
    state.meta = dict(meta)


def run_once(config: dict, state: State, dry_run: bool = False) -> int:
    """Run one polling cycle and return the number of changes that alerted.

    State advances only after an alert is delivered by at least one channel.
    If every delivery attempt fails, the prior state is restored so the next
    cycle can retry the alert.
    """
    statuses_before = dict(state.statuses)
    meta_before = dict(state.meta)

    observed = collect(config["watch"])
    changes = detect_changes(observed, state)

    general = config.get("general", {})
    alert_on_any_change = bool(general.get("alert_on_any_change", False))
    worth_alerting = [c for c in changes if c["actionable"] or alert_on_any_change]

    if not worth_alerting:
        if dry_run:
            _restore_state(state, statuses_before, meta_before)
        else:
            state.save()
        return 0

    alert = build_alert(worth_alerting, config)

    if dry_run:
        _restore_state(state, statuses_before, meta_before)
        LOG.info("dry run — not sending, not saving state")
        print(f"\n--- would send ---\n{alert.title}\n\n{alert.body}\n")
        return len(worth_alerting)

    results = dispatch(config.get("notify", {}), alert)

    if not results or not any(results.values()):
        _restore_state(state, statuses_before, meta_before)
        LOG.error("no notification channel delivered the alert; state was not advanced")
        raise NotificationDeliveryError(
            "no enabled notification channel successfully delivered the alert"
        )

    # At least one channel delivered the message. Save even if another channel
    # failed, otherwise successful channels would be spammed on every cycle.
    state.save()

    failed = sorted(name for name, ok in results.items() if not ok)
    if failed:
        LOG.warning("alert delivered, but these channels failed: %s", ", ".join(failed))

    return len(worth_alerting)
