"""Plain-HTTP source: read schema.org product availability out of a page.

The adapter prefers real JSON-LD parsing over regular expressions. This avoids
accidentally treating unrelated markup as availability while keeping the core
stdlib-only.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Dict, Iterable

from .. import status as st
from ..http import FetchError, fetch


class _JsonLdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_jsonld = False
        self._chunks: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "script":
            return
        values = {str(key).lower(): str(value or "").lower() for key, value in attrs}
        if values.get("type") == "application/ld+json":
            self._in_jsonld = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_jsonld:
            block = "".join(self._chunks).strip()
            if block:
                self.blocks.append(block)
            self._in_jsonld = False
            self._chunks = []


# Fallback for pages that embed availability-like JSON outside proper JSON-LD.
_AVAILABILITY = re.compile(r'"availability"\s*:\s*"([^"]+)"', re.IGNORECASE)
_AVAILABILITY_LIST = re.compile(
    r'"availability"\s*:\s*\[\s*"([^"]+)"', re.IGNORECASE
)

_STATUS_PRIORITY = {
    st.PREORDER: 50,
    st.IN_STOCK: 40,
    st.BACKORDER: 30,
    st.OUT_OF_STOCK: 20,
    st.UNKNOWN: 10,
}


def _walk(value) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, (dict, list)):
            yield from _walk(graph)
        for key, child in value.items():
            if key == "@graph":
                continue
            if isinstance(child, (dict, list)):
                yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _types(node: dict) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return {raw.lower()}
    if isinstance(raw, list):
        return {str(value).lower() for value in raw}
    return set()


def _matches_product(node: dict, needle: str) -> bool:
    if not needle:
        return True
    needle = needle.casefold()
    fields = ("name", "sku", "mpn", "productID", "gtin", "gtin8", "gtin12", "gtin13", "gtin14")
    haystack = " ".join(str(node.get(field, "")) for field in fields).casefold()
    return needle in haystack


def _availability_values(node: dict) -> list[str]:
    values: list[str] = []

    direct = node.get("availability")
    if isinstance(direct, str):
        values.append(direct)
    elif isinstance(direct, list):
        values.extend(str(value) for value in direct if isinstance(value, str))

    offers = node.get("offers")
    if isinstance(offers, dict):
        values.extend(_availability_values(offers))
    elif isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                values.extend(_availability_values(offer))

    return values


def _best_status(values: Iterable[str]) -> str:
    statuses = [st.normalise(value) for value in values]
    statuses = [value for value in statuses if value != st.UNKNOWN]
    if not statuses:
        return st.UNKNOWN
    return max(statuses, key=lambda value: _STATUS_PRIORITY.get(value, 0))


def _from_jsonld(html: str, needle: str) -> str:
    collector = _JsonLdCollector()
    collector.feed(html)

    products: list[dict] = []
    fallback_nodes: list[dict] = []

    for block in collector.blocks:
        try:
            parsed = json.loads(block)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

        for node in _walk(parsed):
            if _availability_values(node):
                fallback_nodes.append(node)
            if "product" in _types(node) and _matches_product(node, needle):
                products.append(node)

    # When a product match was explicitly requested, never fall back to
    # availability belonging to some other product on the same page.
    candidates = products if products else ([] if needle else fallback_nodes)
    values: list[str] = []
    for node in candidates:
        values.extend(_availability_values(node))

    return _best_status(values)


def check(watch: dict) -> Dict[str, str]:
    label = watch.get("label") or "store"
    url = watch["url"]
    needle = str(watch.get("match") or "").strip()

    try:
        html = fetch(url, timeout=int(watch.get("timeout", 25)))
    except FetchError:
        return {label: st.BLOCKED}

    result = _from_jsonld(html, needle)
    if result != st.UNKNOWN:
        return {label: result}

    # A configured match means "this product only". Regex fallback cannot
    # reliably associate an availability token with the requested product,
    # so fail closed instead of risking a false-positive restock.
    if needle:
        return {label: st.UNKNOWN}

    # Some storefronts expose JSON-like availability outside application/ld+json.
    values = _AVAILABILITY.findall(html) + _AVAILABILITY_LIST.findall(html)
    return {label: _best_status(values)}
