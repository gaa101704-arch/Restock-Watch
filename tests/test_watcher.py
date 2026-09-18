"""Tests for the parts that decide whether you get woken up at 3am.

Run with: python3 -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from restock_watch import status as st  # noqa: E402
from restock_watch import watcher  # noqa: E402
from restock_watch.sources import jsonld, nowinstock  # noqa: E402
from restock_watch.state import State  # noqa: E402


class TestNormalise(unittest.TestCase):
    def test_schema_org_urls(self):
        self.assertEqual(st.normalise("https://schema.org/InStock"), st.IN_STOCK)
        self.assertEqual(st.normalise("https://schema.org/OutOfStock"), st.OUT_OF_STOCK)
        self.assertEqual(st.normalise("https://schema.org/PreOrder"), st.PREORDER)
        self.assertEqual(st.normalise("https://schema.org/BackOrder"), st.BACKORDER)

    def test_buy_box_wording(self):
        self.assertEqual(st.normalise("Pre-order now"), st.PREORDER)
        self.assertEqual(st.normalise("Currently unavailable"), st.OUT_OF_STOCK)
        self.assertEqual(st.normalise("In Stock"), st.IN_STOCK)

    def test_schema_org_orderable_variants_are_in_stock(self):
        self.assertEqual(st.normalise("LimitedAvailability"), st.IN_STOCK)
        self.assertEqual(st.normalise("MadeToOrder"), st.IN_STOCK)

    def test_nothing_useful(self):
        self.assertEqual(st.normalise(""), st.UNKNOWN)
        self.assertEqual(st.normalise("banana"), st.UNKNOWN)


class TestDetectChanges(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = State(Path(self._tmp.name) / "state.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_first_sighting_is_a_baseline_not_an_alert(self):
        changes = watcher.detect_changes({"A": st.PREORDER}, self.state)
        self.assertEqual(changes, [])
        self.assertEqual(self.state.get("A"), st.PREORDER)

    def test_restock_is_reported_once(self):
        watcher.detect_changes({"A": st.OUT_OF_STOCK}, self.state)
        first = watcher.detect_changes({"A": st.IN_STOCK}, self.state)
        second = watcher.detect_changes({"A": st.IN_STOCK}, self.state)
        self.assertEqual(len(first), 1)
        self.assertTrue(first[0]["actionable"])
        self.assertEqual(second, [])

    def test_a_preorder_opening_is_an_actionable_alert(self):
        # Deliberate product decision, pinned so a refactor cannot quietly
        # drop PREORDER from ACTIONABLE: for pre-release hardware the
        # pre-order window is the event people install this to catch.
        watcher.detect_changes({"A": st.OUT_OF_STOCK}, self.state)
        changes = watcher.detect_changes({"A": st.PREORDER}, self.state)

        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0]["actionable"])
        self.assertIn(st.PREORDER, st.ACTIONABLE)

    def test_a_preorder_alert_says_preorder_not_in_stock(self):
        changes = [
            {"target": "Target", "from": "OUT_OF_STOCK", "to": st.PREORDER, "actionable": True}
        ]
        alert = watcher.build_alert(changes, {"general": {"product_name": "Widget"}})
        self.assertTrue(alert.actionable)
        self.assertIn("PREORDER: Widget", alert.title)

    def test_blocked_never_clobbers_a_known_status(self):
        watcher.detect_changes({"A": st.IN_STOCK}, self.state)
        changes = watcher.detect_changes({"A": st.BLOCKED}, self.state)
        self.assertEqual(changes, [])
        self.assertEqual(self.state.get("A"), st.IN_STOCK)

    def test_captcha_then_normal_page_is_not_a_restock(self):
        watcher.detect_changes({"A": st.OUT_OF_STOCK}, self.state)
        watcher.detect_changes({"A": st.BLOCKED}, self.state)
        changes = watcher.detect_changes({"A": st.OUT_OF_STOCK}, self.state)
        self.assertEqual(changes, [])

    def test_going_out_of_stock_is_a_change_but_not_actionable(self):
        watcher.detect_changes({"A": st.IN_STOCK}, self.state)
        changes = watcher.detect_changes({"A": st.OUT_OF_STOCK}, self.state)
        self.assertEqual(len(changes), 1)
        self.assertFalse(changes[0]["actionable"])


class TestStatePersistence(unittest.TestCase):
    def test_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "state.json"
            first = State(path)
            first.set("A", st.PREORDER)
            first.save()
            self.assertEqual(State(path).get("A"), st.PREORDER)

    def test_corrupt_state_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{ not json")
            self.assertEqual(State(path).statuses, {})


class TestNowInStockParser(unittest.TestCase):
    """Parsed against markup captured from the live tracker.

    The fixture pins down the contract that matters: every Zelda row on the
    real page is class="offRow", and the actual status lives in a
    <td class="stockStatus*"> cell. Target was showing Preorder at capture
    time while sharing a row class with the out-of-stock rows.
    """

    FIXTURES = Path(__file__).resolve().parent / "fixtures"
    PRODUCT = "Legend of Zelda 40th Anniversary Edition"

    def setUp(self):
        self._real_fetch = nowinstock.fetch
        self.sample = (
            self.FIXTURES / "nowinstock_switch2_zelda_2026-09-17.html"
        ).read_text()
        nowinstock.fetch = lambda *a, **k: self.sample

    def tearDown(self):
        nowinstock.fetch = self._real_fetch

    def test_reads_the_status_cell_not_the_row_class(self):
        result = nowinstock.check({"url": "x", "match": self.PRODUCT, "label": "nis"})
        self.assertEqual(
            result,
            {
                "nis:Amazon": st.OUT_OF_STOCK,
                "nis:Best Buy": st.OUT_OF_STOCK,
                "nis:Nintendo Store": st.OUT_OF_STOCK,
                "nis:Target": st.PREORDER,
                "nis:Walmart": st.OUT_OF_STOCK,
            },
        )

    def test_a_preorder_is_not_reported_as_out_of_stock(self):
        # The regression this fixture exists for: reading the row class alone
        # reported OUT_OF_STOCK here, so the pre-order never alerted.
        result = nowinstock.check(
            {"url": "x", "match": self.PRODUCT, "label": "nis", "retailers": ["Target"]}
        )
        self.assertEqual(result, {"nis:Target": st.PREORDER})
        self.assertIn(result["nis:Target"], st.ACTIONABLE)

    def test_fixture_preserves_the_misleading_row_class(self):
        # Guards against a future "tidy-up" reintroducing class-based parsing
        # because a hand-written fixture happened to agree with it.
        self.assertIn('class="offRow"', self.sample)
        self.assertNotIn('class="preorder"', self.sample)
        self.assertIn("stockStatusPre", self.sample)

    def test_retailer_filter(self):
        result = nowinstock.check(
            {"url": "x", "match": self.PRODUCT, "label": "nis", "retailers": ["Best Buy"]}
        )
        self.assertEqual(result, {"nis:Best Buy": st.OUT_OF_STOCK})

    def test_unrelated_products_on_the_same_page_are_excluded(self):
        result = nowinstock.check({"url": "x", "match": self.PRODUCT, "label": "nis"})
        self.assertEqual(len(result), 5)

    def test_fetch_failure_returns_nothing_rather_than_out_of_stock(self):
        from restock_watch.http import FetchError

        def boom(*a, **k):
            raise FetchError("down")

        nowinstock.fetch = boom
        self.assertEqual(nowinstock.check({"url": "x", "match": self.PRODUCT}), {})


class TestJsonLdParser(unittest.TestCase):
    FIXTURES = Path(__file__).resolve().parent / "fixtures"

    def setUp(self):
        self._real_fetch = jsonld.fetch

    def tearDown(self):
        jsonld.fetch = self._real_fetch

    def test_captured_nintendo_page_parses_by_sku(self):
        # Real markup from the live store page, matched on the store's own SKU.
        html = (self.FIXTURES / "nintendo_switch2_zelda_2026-09-17.html").read_text()
        jsonld.fetch = lambda *a, **k: html
        self.assertEqual(
            jsonld.check({"url": "x", "label": "Nintendo", "match": "121642"}),
            {"Nintendo": st.OUT_OF_STOCK},
        )

    def test_captured_page_fails_closed_on_a_wrong_sku(self):
        # A match that names a different product must never borrow this one's
        # availability — better to say nothing than to alert about the wrong item.
        html = (self.FIXTURES / "nintendo_switch2_zelda_2026-09-17.html").read_text()
        jsonld.fetch = lambda *a, **k: html
        self.assertEqual(
            jsonld.check({"url": "x", "label": "Nintendo", "match": "999999"}),
            {"Nintendo": st.UNKNOWN},
        )

    def test_product_without_any_availability_is_unknown(self):
        html = (self.FIXTURES / "synthetic_product_without_availability.html").read_text()
        jsonld.fetch = lambda *a, **k: html
        self.assertEqual(
            jsonld.check({"url": "x", "label": "Nintendo", "match": "Zelda"}),
            {"Nintendo": st.UNKNOWN},
        )

    def test_prefers_matching_product_jsonld(self):
        html = """
        <script type="application/ld+json">
        {
          "@graph": [
            {"@type":"Product","name":"Other Widget","offers":{"availability":"https://schema.org/InStock"}},
            {"@type":"Product","name":"Target Widget","offers":{"availability":"https://schema.org/OutOfStock"}}
          ]
        }
        </script>
        """
        jsonld.fetch = lambda *a, **k: html
        result = jsonld.check({"url": "x", "label": "store", "match": "Target Widget"})
        self.assertEqual(result, {"store": st.OUT_OF_STOCK})

    def test_requested_product_does_not_fall_back_to_another_product(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Other Widget","offers":{"availability":"https://schema.org/InStock"}}
        </script>
        """
        jsonld.fetch = lambda *a, **k: html
        self.assertEqual(
            jsonld.check({"url": "x", "label": "store", "match": "Target Widget"}),
            {"store": st.UNKNOWN},
        )

    def test_malformed_jsonld_falls_back_without_crashing(self):
        html = """
        <script type="application/ld+json">{ definitely not json }</script>
        <div data-state='{"availability":"https://schema.org/PreOrder"}'></div>
        """
        jsonld.fetch = lambda *a, **k: html
        self.assertEqual(
            jsonld.check({"url": "x", "label": "store"}),
            {"store": st.PREORDER},
        )


class TestWatcherReliability(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = State(Path(self._tmp.name) / "state.json")
        self._real_collect = watcher.collect
        self._real_dispatch = watcher.dispatch

    def tearDown(self):
        watcher.collect = self._real_collect
        watcher.dispatch = self._real_dispatch
        self._tmp.cleanup()

    def test_collect_rejects_invalid_source_status(self):
        real_get_source = watcher.get_source
        try:
            watcher.get_source = lambda name: (lambda watch: {"A": "NOT_A_STATUS"})
            self.assertEqual(
                watcher.collect([{"source": "fake", "label": "fake"}]),
                {"A": st.UNKNOWN},
            )
        finally:
            watcher.get_source = real_get_source

    def test_dry_run_does_not_mutate_in_memory_state(self):
        self.state.set("A", st.OUT_OF_STOCK)
        watcher.collect = lambda watches: {"A": st.IN_STOCK}
        config = {
            "watch": [{"source": "fake"}],
            "notify": {"console": {"enabled": True}},
            "general": {"product_name": "Widget"},
        }
        watcher.run_once(config, self.state, dry_run=True)
        self.assertEqual(self.state.get("A"), st.OUT_OF_STOCK)

    def test_all_notification_failures_restore_state_for_retry(self):
        self.state.set("A", st.OUT_OF_STOCK)
        watcher.collect = lambda watches: {"A": st.IN_STOCK}
        watcher.dispatch = lambda channel_config, alert: {"webhook": False}
        config = {
            "watch": [{"source": "fake"}],
            "notify": {"webhook": {"enabled": True}},
            "general": {"product_name": "Widget"},
        }

        with self.assertRaises(watcher.NotificationDeliveryError):
            watcher.run_once(config, self.state)

        self.assertEqual(self.state.get("A"), st.OUT_OF_STOCK)


class TestAlertBody(unittest.TestCase):
    def test_actionable_alert_names_the_product_and_links(self):
        changes = [{"target": "Best Buy", "from": "OUT_OF_STOCK", "to": "IN_STOCK", "actionable": True}]
        config = {"general": {"product_name": "Widget", "links": ["https://example.com/buy"]}}
        alert = watcher.build_alert(changes, config)
        self.assertIn("IN STOCK: Widget", alert.title)
        self.assertIn("https://example.com/buy", alert.body)
        self.assertTrue(alert.actionable)
        self.assertEqual(json.loads(json.dumps(alert.as_dict()))["changes"], changes)


class TestCollectMergesSources(unittest.TestCase):
    """Two sources reporting the same target.

    The rule that matters: UNKNOWN and BLOCKED mean "this source learned
    nothing". They must never cancel out a source that did learn something,
    or a bot-walled second check silently swallows the restock alert.
    """

    def setUp(self):
        self._real_get_source = watcher.get_source

    def tearDown(self):
        watcher.get_source = self._real_get_source

    def _collect(self, first, second):
        results = iter(({"A": first}, {"A": second}))
        watcher.get_source = lambda name: (lambda watch: next(results))
        return watcher.collect(
            [{"source": "one", "label": "one"}, {"source": "two", "label": "two"}]
        )["A"]

    def test_blocked_does_not_veto_a_real_reading(self):
        self.assertEqual(self._collect(st.IN_STOCK, st.BLOCKED), st.IN_STOCK)

    def test_real_reading_replaces_an_earlier_blocked(self):
        self.assertEqual(self._collect(st.BLOCKED, st.IN_STOCK), st.IN_STOCK)

    def test_unknown_does_not_veto_a_real_reading(self):
        self.assertEqual(self._collect(st.PREORDER, st.UNKNOWN), st.PREORDER)

    def test_two_sources_that_both_claim_to_know_and_disagree(self):
        self.assertEqual(self._collect(st.IN_STOCK, st.OUT_OF_STOCK), st.UNKNOWN)

    def test_agreement_is_passed_through(self):
        self.assertEqual(self._collect(st.OUT_OF_STOCK, st.OUT_OF_STOCK), st.OUT_OF_STOCK)

    def test_two_uninformative_readings_stay_uninformative(self):
        self.assertIn(self._collect(st.BLOCKED, st.UNKNOWN), st.UNINFORMATIVE)


class TestCliExitCodes(unittest.TestCase):
    """A delivery failure is an operational event, not a crash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._real_collect = watcher.collect
        self._real_dispatch = watcher.dispatch

    def tearDown(self):
        watcher.collect = self._real_collect
        watcher.dispatch = self._real_dispatch
        self._tmp.cleanup()

    def _config_file(self) -> Path:
        path = Path(self._tmp.name) / "config.toml"
        path.write_text(
            "[general]\n"
            'product_name = "Widget"\n'
            "interval_seconds = 300\n"
            f'state_file = "{Path(self._tmp.name) / "state.json"}"\n'
            "[[watch]]\n"
            'source = "jsonld"\n'
            'url = "https://example.invalid/thing"\n'
            'label = "A"\n'
            "[notify.webhook]\n"
            "enabled = true\n"
            'url = "http://127.0.0.1:9/nope"\n'
        )
        return path

    def test_total_delivery_failure_exits_cleanly(self):
        from restock_watch.__main__ import EXIT_DELIVERY_FAILED, main

        state = State(Path(self._tmp.name) / "state.json")
        state.set("A", st.OUT_OF_STOCK)
        state.save()

        watcher.collect = lambda watches: {"A": st.IN_STOCK}
        watcher.dispatch = lambda channel_config, alert: {"webhook": False}

        # No exception escapes to the user, and the code is one a cron or
        # systemd wrapper can act on.
        self.assertEqual(main(["-c", str(self._config_file())]), EXIT_DELIVERY_FAILED)

        # State was not advanced, so the next cycle retries the alert.
        self.assertEqual(State(Path(self._tmp.name) / "state.json").get("A"), st.OUT_OF_STOCK)


if __name__ == "__main__":
    unittest.main()
