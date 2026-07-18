# Project ledger

Use this as the shared handoff note for agents working in this repository. Update it when starting, completing, or blocking a meaningful piece of work.

## Current focus

Make the e-book MVP browser page a reliable layout workbench for the fixed-layout EPUB export.

## Completed

- Created the `feature/ebook-epub-preview` branch for the EPUB-preview work.
- Reworked `ebook.html` into a 1200 × 1800 fixed-page EPUB preview with chapter overview and section-page selection.
- Added `assets/epub-layout.css` as the shared stylesheet for the browser preview and `scripts/generate_epub.py` export.
- Reduced fixed-page title and Japanese/ruby type sizes to make short articles more likely to fit on one overview page.
- Changed overview section layout from distributed spacing to a fixed 18px gap, preventing short articles from being stretched vertically.
- Counted current article body lengths. Six articles exceed the 500-character target:
  - `2026-07-17-shinkansen-suica-seats` — 718
  - `2026-07-18-train-stop-position` — 712
  - `2026-07-16-seven-eleven-japan` — 683
  - `2026-07-14-japan-v2x-usage` — 615
  - `2026-07-15-blinker-thank-you` — 589
  - `2026-07-13-etc-everywhere-tokyo` — 568

## Next todos

- Manually inspect the EPUB preview at desktop and mobile widths, especially long titles and 450–500 character articles.
- Export and inspect the EPUB in the target reader(s); fixed-layout CSS support can vary by reader.
- Decide whether to shorten the six over-limit articles or allow them to use a multi-page overview treatment.
- Remove the now-unreachable legacy stylesheet literal in `scripts/generate_epub.py` after confirming the shared stylesheet is accepted by all EPUB readers.

## Validation run

- `node --check assets/ebook.js`
- `python3 -m py_compile scripts/generate_epub.py scripts/generate_site.py`
- `python3 scripts/generate_site.py`
- Verified `book_stylesheet()` loads `assets/epub-layout.css`.
- `git diff --check`

## Working-tree note

The worktree contained pre-existing generated-page and e-book MVP changes before this ledger was added. Preserve unrelated edits.
