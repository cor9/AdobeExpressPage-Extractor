# Adobe Express page extractor

An internal archival tool for Child Actor 101. It takes a **public Adobe Express (Spark) page**
and turns it into a small, version-controlled description of that page (a *spec*), plus local copies of
its images and styling, so the site can re-render the original page very closely in React without
depending on Adobe. It is how the **NO EXCUSES!** and **The Perfect Self Tape** courses (17 pages)
were restored. Keep it: other surviving Adobe pages can be archived the same way.

## 1. What it does

For one page it records, in original order:

- headings, paragraphs, lists, quotes (with inline bold/italic/links), buttons and links
- images with their display sizing, captions, and the copy Adobe stores in a figure's `aria-label`
- video embeds in their exact positions (see §6)
- section types: single column, full-width photo, split layout, window band, full-screen photo, photo
  grid, card flip-book, spacers, title section (background photo + title), author/credits
- the page's **theme CSS** (re-scoped so pages cannot collide), the **Adobe Fonts** it uses, and any
  assets its theme references
- links to other archived pages, rewritten to local routes (`page_routes.py`)

The live page's markup is the source of truth. Nothing is rewritten or "improved".

## 2. Input

A public page URL on either Adobe host:

- `https://express.adobe.com/page/<ID>/` (classic Spark pages)
- `https://new.express.adobe.com/webpage/<ID>` (newer Adobe Express webpages)

plus a **course** name (the folder and the `/courses/<course>/` route) and a **slug** (the page name;
use `index` for a course's hub page, served at `/courses/<course>`). Python 3, standard library only.
It downloads the page itself; `--html FILE` uses a saved copy instead.

## 3. Run it

From the repository root:

```bash
python3 scripts/adobe-extractor/adobe_page_to_spec.py \
  https://express.adobe.com/page/<ID>/ my-course my-page
```

Options: `--image-size 2560` (default; max pixel width of stored images, Adobe resizes server-side) or
`--image-size orig` for original files, and `--html FILE`. To re-archive every page listed in
`manifest.json`: `python3 scripts/adobe-extractor/adobe_page_to_spec.py --manifest scripts/adobe-extractor/manifest.json`.
Re-running is safe: images already stored are skipped and outputs are deterministic. Record each new page in
`manifest.json` and add its Adobe page id to `page_routes.py` (so sibling pages link to it locally).

Then add the route (one small file per page; copy any `src/app/courses/<course>/<slug>/page.tsx`):

```tsx
import "@/content/adobe/<course>/<slug>.theme.css";            // import the theme CSS first
import { AdobePage } from "@/components/adobe/AdobePage";
import type { AdobePageSpec } from "@/components/adobe/AdobePage";
import spec from "@/content/adobe/<course>/<slug>.json";
export default function Page() { return <AdobePage spec={spec as AdobePageSpec} />; }
```

(Optionally add `AdobeCourseNav` for previous/next links; see the existing course pages.)

## 4. What it produces

| Output | Purpose |
|---|---|
| `src/content/adobe/<course>/<slug>.json` | the ordered page spec |
| `src/content/adobe/<course>/<slug>.theme.css` | the page's theme CSS, scoped to `.adobe-theme-<course>-<slug>` |
| `public/courses/<course>/<slug>/images/*` | every image on the page |
| `public/courses/<course>/<slug>/theme/*` | assets referenced by the theme CSS (only for built-in themes) |

Spec shape: `{ source, theme, fontKits[], title, sections[], author?, credits?, runtime }`.
`sections[]` items have a `kind` (`single-column`, `full-width`, `split`, `window`, `fullscreen`,
`photo-grid`, `flipbook`, `spacer`), the original `classes`, and `elements[]`. Element types: `h2/h3/h4/p/
blockquote` (inline HTML), `ul/ol`, `button`, `image`, `video`, and `raw` (a safe fallback for anything the
extractor does not recognise; nothing is silently dropped). The TypeScript types are in
`src/components/adobe/AdobePage.tsx`.

## 5. How the site renders it

- `src/components/adobe/AdobePage.tsx` turns a spec into markup that mirrors Adobe's own DOM
  (`.section > .section-view > .section-content > .content-container`, `.image`, `.link-button-wrapper`, ...), so the
  page's theme CSS applies unchanged. It also links the page's Adobe Fonts kits.
- `src/components/adobe/adobe-layout.css` reproduces the parts of Adobe's runtime layout that the original page got
  from Adobe's JavaScript/runtime stylesheet (section stacking, split layout, photo-grid tile positions, ...). It
  is deliberately written at the same low specificity as Adobe's runtime so each page's theme wins, as on the original.
- `RevealOnScroll.tsx` re-creates the scroll fade-in; `AdobeCourseNav.tsx` is the previous/next bar.
- Pages with an older Adobe runtime (1.22) scale inline images to the column; newer ones (1.23+, Adobe Express webpages)
  show them at their loaded size. The extractor records `runtime: "classic" | "new"` and `displayWidth` accordingly.

## 6. Video handling

The original pages embedded Vimeo videos, which Corey migrated to Bunny Stream (library `712901`, see
`src/lib/bunny.ts`). `video_map.py` is the single place that decides what each Vimeo id becomes:

- **Mapped to Bunny** (`bunny(guid, title)`): rendered as the Bunny player. `review=True` marks a
  medium-confidence match worth double-checking.
- **Third-party** (`external_vimeo(...)` for a still-live Vimeo video, `youtube(id, title)` for a Vimeo embed replaced by a YouTube video, and any YouTube embed): the original
  embed is preserved as-is.
- **Unresolved** (`missing(...)`, or any Vimeo id not in the map; none remain in the 17 current pages): a neutral gray "Video coming soon" box in the exact
  original position, with the legacy Vimeo id kept in the spec and `data-legacy-vimeo` on the element.
  Placeholders have an anchor: `/courses/<course>/<slug>#video-N` jumps to the Nth video on the page.

To fill a placeholder: replace its `missing(...)` entry with `bunny("<guid>", "<title>")` in `video_map.py` and
re-run the extractor for the pages containing it. Nothing is guessed; unknown videos stay placeholders. `vimeo_library.csv` is an export of Corey's Vimeo library
(id, title, duration); match a legacy id's Vimeo title to the Bunny title before mapping it, and check durations when titles are generic.

## 7. Network access needed

Only when extracting (the finished site serves everything locally except fonts and videos):

- `express.adobe.com`, `new.express.adobe.com` (the pages and their images)
- `page.adobespark-assets.com` (runtime/theme CSS and font scripts for classic pages)
- `use.typekit.net` (Adobe Fonts kit CSS and font files, also loaded by the site at runtime)

At runtime the site additionally embeds `iframe.mediadelivery.net` (Bunny), `www.youtube.com` and
`player.vimeo.com`. In a locked-down environment these hosts must be allowed or the checks cannot see them.

## 8. Known limitations

- It archives what the public page serves. It does not render the page in a browser; behaviour Adobe produces with
  JavaScript is re-implemented by hand in `adobe-layout.css` / `AdobePage.tsx`.
- **Card flip-book** sections (cards that advance over a pinned photo as you scroll) are rendered as one full-screen
  band per card, in order, not as a scroll-driven animation. **Photo grids** are static (no lightbox);
  **images** open no large-preview viewer. Adobe's footer ("Appreciate", Terms, Report Abuse) is intentionally dropped.
- Section types it has not seen (pull quotes, glideshows, other layouts) are skipped at the section level; unknown
  *elements* inside known sections are kept as `raw`. Run `checks/compare-to-live.cjs` to find out.
- Themes depend on Adobe Fonts kits that Adobe can change or retire; the site links them rather than storing font files.
- Copy that Adobe stored only as image text (common on newer Express pages) stays image text.
- Mobile layout comes from the page's own theme CSS (plus the split-layout stacking rules); it has been compared with the
  originals only for overflow, not measured at phone width.

## 9. Adding support for a new section or layout type

1. **Find it.** Re-run the extractor and open the page. Compare with the original using
   `node scripts/adobe-extractor/checks/compare-to-live.cjs <live-url> <local-url>`; missing or mis-sized content points at it.
   In the original page's HTML, the section is a `div.section.<kind>-section` inside `div.article`.
2. **Extract it.** In `adobe_page_to_spec.py`, add a branch in `PageExtractor.parse_sections` (and a small
   helper like `_photo_grid_section`) that records the section's `kind`, `classes`, and its content in the spec. Use
   `elements_in(container)` for ordinary content, `background(section)` for a background photo, and `fetch_image` for any
   image so it is stored locally.
3. **Render it.** In `AdobePage.tsx`, add the kind to the `AdobeSection` type and a branch in the section loop that
   emits Adobe's own class names. If the original relied on Adobe's runtime for layout, copy the relevant rules from the
   page's runtime stylesheet (`<runtime>/runtime.gz.css`, linked in the page's `<head>`) into `adobe-layout.css`, wrapped in
   `:where(.adobe-page)` so they stay lower-specificity than page themes.
4. **Verify.** Run `compare-to-live.cjs` (aim for `element diffs: 0`), `checks/verify-pages.cjs <base-url>`, and `npm run build`.

## Files

| File | Role |
|---|---|
| `adobe_page_to_spec.py` | the extractor |
| `video_map.py` | Vimeo id -> Bunny / third-party / placeholder |
| `vimeo_library.csv` | Vimeo id -> original title/duration, for confirming Bunny matches |
| `page_routes.py` | Adobe page id -> local route (internal links) |
| `manifest.json` | pages archived so far (re-run them all with `--manifest`) |
| `checks/compare-to-live.cjs` | measure a recreated page against the live original |
| `checks/verify-pages.cjs` | browser smoke test of every archived page (images, console, overflow, embeds) |

(`scripts/build_courses_from_adobe.py` is an obsolete earlier generator, kept only until cleanup; it now reads
the same `video_map.py`.)
