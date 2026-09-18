# HTML fixtures

These files are intentionally small, sanitized snapshots derived from live
retailer/tracker observations. They preserve only the markup and product/status
details needed by the parser tests.

They are not full copies of third-party pages. Scripts, branding, affiliate
links, analytics, unrelated products, and site chrome are removed.

Current provenance:

- `nowinstock_switch2_zelda_out_2026-09-17.html`: live NowInStock Nintendo Switch 2 tracker, Zelda 40th Anniversary Edition rows observed out of stock on 2026-09-17.
- `nowinstock_switch2_zelda_preorder_2026-09-17.html`: sanitized row representing a preorder state shown in the same tracker's status history on 2026-09-17.
- `nintendo_switch2_zelda_no_availability_2026-09-17.html`: Nintendo product-page metadata observed on 2026-09-17, with no reliable availability signal retained.

When retailer markup changes, add a new dated fixture rather than silently
rewriting an old one. That keeps regressions reproducible.
