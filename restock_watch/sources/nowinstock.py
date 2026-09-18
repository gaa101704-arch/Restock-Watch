"""Multi-retailer source: scrape a NowInStock tracker page.

One fetch gives you Amazon, Best Buy, Target and Walmart at once, which is
why it is worth having alongside a first-party check. It lags the retailer
by a little, so treat it as breadth rather than as your fastest signal.
"""

from __future__ import annotations

import re
from typing import Dict

from .. import status as st
from ..http import FetchError, fetch

_ROW = re.compile(r'<tr id="tr\d+"[^>]*class="([\w\s-]+)"[^>]*>(.*?)</tr>', re.DOTALL)
_RETAILER = re.compile(r">[^<]*:\s*([\w][\w\s./&\'-]+)</a>")
_TAG = re.compile(r"<[^>]+>")

# The real status lives in a dedicated cell. The row's own class is only a
# coarse highlight: a row showing "Preorder" is still class="offRow", so
# reading the row class alone reports OUT_OF_STOCK and misses the pre-order
# entirely — which on a pre-release console is the whole point.
_STATUS_CELL = re.compile(
    r'<td[^>]*class="[^"]*(stockStatus\w*)[^"]*"[^>]*>(.*?)</td>',
    re.DOTALL | re.IGNORECASE,
)

_CELL_CLASS_STATUS = {
    "stockstatusin": st.IN_STOCK,
    "stockstatusavailable": st.IN_STOCK,
    "stockstatuspre": st.PREORDER,
    "stockstatusorder": st.PREORDER,
    "stockstatusback": st.BACKORDER,
    "stockstatusout": st.OUT_OF_STOCK,
}


def _status_from_row_class(row_class: str) -> str:
    """Fallback only, for markup with no status cell."""
    css = row_class.lower()
    if "preorder" in css:
        return st.PREORDER
    if "onrow" in css:
        return st.IN_STOCK
    if "offrow" in css or "off" in css:
        return st.OUT_OF_STOCK
    return st.UNKNOWN


def _status_from_row(row_html: str, row_class: str) -> str:
    """Prefer the status cell; fall back to the row class."""
    cell = _STATUS_CELL.search(row_html)
    if cell:
        mapped = _CELL_CLASS_STATUS.get(cell.group(1).lower())
        if mapped:
            return mapped
        # Unrecognised class: the visible label is the next best evidence.
        text = _TAG.sub(" ", cell.group(2)).strip()
        from_text = st.normalise(text)
        if from_text != st.UNKNOWN:
            return from_text

    return _status_from_row_class(row_class)


def check(watch: dict) -> Dict[str, str]:
    url = watch["url"]
    # Only rows containing this string are tracked, so one tracker page can
    # host several products without them bleeding into each other.
    needle = (watch.get("match") or "").lower()
    prefix = watch.get("label") or "nowinstock"
    only = {r.lower() for r in watch.get("retailers", [])}

    try:
        html = fetch(url, timeout=int(watch.get("timeout", 25)))
    except FetchError:
        return {}

    results: Dict[str, str] = {}
    for row_class, row_html in _ROW.findall(html):
        text = _TAG.sub(" ", row_html)
        if needle and needle not in text.lower():
            continue
        retailer_match = _RETAILER.search(row_html)
        if not retailer_match:
            continue
        retailer = retailer_match.group(1).strip()
        if only and retailer.lower() not in only:
            continue
        results[f"{prefix}:{retailer}"] = _status_from_row(row_html, row_class)

    return results
