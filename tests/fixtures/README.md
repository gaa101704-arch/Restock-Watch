# HTML fixtures

Small snapshots the parser tests run against, so a retailer changing their
markup shows up as a failing test rather than as silence on the day something
restocks.

## Captured fixtures

These are real markup, taken from the live page on the date in the filename.
Affiliate and tracking URLs are replaced with `example.invalid` and page
chrome is removed, but **the structures the parser reads are preserved
exactly as served**. That is the whole point: a fixture that has been tidied
into the shape the parser expects tests nothing.

- `nowinstock_switch2_zelda_2026-09-17.html` — the five Zelda 40th Anniversary
  Edition rows from the NowInStock Switch 2 tracker. Every row is
  `class="offRow"`, while Target's `<td class="stockStatusPre">` says
  `Preorder`. **The row class is not the status.** Reading the row class alone
  reports Target as out of stock and never alerts on the pre-order, which is
  the bug this fixture exists to prevent from coming back.
- `nintendo_switch2_zelda_2026-09-17.html` — the Nintendo store page's single
  `application/ld+json` block, verbatim: a Product with `sku: "121642"` and an
  Offer whose availability was `OutOfStock` at capture time.

## Synthetic fixtures

Hand-written, and named so you can tell. Fine for pinning down a behaviour, as
long as nobody mistakes one for evidence about how a real site behaves.

- `synthetic_product_without_availability.html` — a Product with no offers and
  no availability, to check that absence reads as `UNKNOWN` rather than
  `OUT_OF_STOCK`.

## Adding one

Capture it, do not compose it. Save the page while the product is out of
stock, and again if you ever catch it in stock or on pre-order; those two
files are worth more than any amount of careful reading, because retailer
markup changes without warning and rarely in the way you would have guessed.

When markup changes, add a new dated fixture rather than rewriting an old one.
That keeps regressions reproducible.
