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
    FIXTURES = Path(__file__).resolve().parent / "fixtures"

    def setUp(self):
        self._real_fetch = nowinstock.fetch
        self.sample = (self.FIXTURES / "nowinstock_switch2_zelda_preorder_2026-09-17.html").read_text()
        nowinstock.fetch = lambda *a, **k: self.sample

    def tearDown(self):
        nowinstock.fetch = self._real_fetch

    def test_matches_only_the_requested_product(self):
        result = nowinstock.check({"url": "x", "match": "Zelda", "label": "nis"})
        self.assertEqual(
            result, {"nis:Amazon": st.PREORDER, "nis:Best Buy": st.OUT_OF_STOCK}
        )

    def test_retailer_filter(self):
        result = nowinstock.check(
            {"url": "x", "match": "Zelda", "label": "nis", "retailers": ["Best Buy"]}
        )
        self.assertEqual(result, {"nis:Best Buy": st.OUT_OF_STOCK})

    def test_live_derived_out_of_stock_fixture_filters_unrelated_product(self):
        html = (self.FIXTURES / "nowinstock_switch2_zelda_out_2026-09-17.html").read_text()
        nowinstock.fetch = lambda *a, **k: html
        result = nowinstock.check({"url": "x", "match": "Zelda", "label": "nis"})
        self.assertEqual(
            result,
            {
                "nis:Amazon": st.OUT_OF_STOCK,
                "nis:Best Buy": st.OUT_OF_STOCK,
                "nis:Nintendo Store": st.OUT_OF_STOCK,
                "nis:Target": st.OUT_OF_STOCK,
                "nis:Walmart": st.OUT_OF_STOCK,
            },
        )

    def test_fetch_failure_returns_nothing_rather_than_out_of_stock(self):
        from restock_watch.http import FetchError

        def boom(*a, **k):
            raise FetchError("down")

        nowinstock.fetch = boom
        self.assertEqual(nowinstock.check({"url": "x", "match": "Zelda"}), {})


class TestJsonLdParser(unittest.TestCase):
    FIXTURES = Path(__file__).resolve().parent / "fixtures"

    def setUp(self):
        self._real_fetch = jsonld.fetch

    def tearDown(self):
        jsonld.fetch = self._real_fetch

    def test_live_derived_nintendo_page_without_availability_is_unknown(self):
        html = (self.FIXTURES / "nintendo_switch2_zelda_no_availability_2026-09-17.html").read_text()
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


if __name__ == "__main__":
    unittest.main()
