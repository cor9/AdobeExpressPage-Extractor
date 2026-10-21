# Adobe Express Page Extractor

An archival tool that takes a public Adobe Express (Spark) page and turns it into a small, version-controlled JSON specification, plus local copies of its images and styling. This allows you to re-render the original page very closely in React without depending on Adobe's servers. It is ideal for preserving legacy content, restoring archived pages, or migrating off the platform.

---

## 1. What It Does

For a given page, it records the following in original order:

* **Headings, paragraphs, lists, and quotes** (preserving inline bold, italic, and links), buttons, and links.
* **Images** with their display sizing, captions, and the copy Adobe stores in a figure's `aria-label`.
* **Video embeds** in their exact positions (see [§6. Video Handling](#6-video-handling)).
* **Section types**: single column, full-width photo, split layout, window band, full-screen photo, photo grid, card flip-book, spacers, title section (background photo + title), and author/credits.
* **Theme styling**: the page's theme CSS (re-scoped so pages cannot collide), the Adobe Fonts it uses, and any assets its theme references.
* **Internal linking**: links to other archived pages, rewritten to local routes via `page_routes.py`.

The live page's markup is the source of truth. Nothing is rewritten or "improved".

---

## 2. Input

A public page URL on either Adobe host:
* `https://express.adobe.com/page/<ID>/` (classic Spark pages)
* `https://new.express.adobe.com/webpage/<ID>` (newer Adobe Express webpages)

You also specify a category/collection folder name and a slug (use `index` for a hub/landing page).

**Prerequisites:** Python 3 (standard library only; no pip dependencies required). It downloads the page directly, or you can supply `--html FILE` to parse a saved local copy.

---

## 3. Usage

Run from the repository root:

`python3 scripts/adobe-extractor/adobe_page_to_spec.py \
  https://express.adobe.com/page/<ID>/ <category> <slug>`

### CLI Options

* `--image-size 2560`: (Default) Maximum pixel width of stored images (Adobe resizes server-side). Use `--image-size orig` to pull raw original files.
* `--html FILE`: Extract from a local `.html` file instead of fetching over the network.
* `--manifest FILE`: Re-archive every page listed in a manifest file (e.g., `python3 scripts/adobe-extractor/adobe_page_to_spec.py --manifest scripts/adobe-extractor/manifest.json`).

> **Note:** Re-running the extractor is idempotent: images already downloaded locally are skipped, and spec output is deterministic. Record each page in `manifest.json` and add its Adobe page ID to `page_routes.py` so sibling pages link to each other locally.

### Adding the Route to React / Next.js

Add a route component for each extracted page (e.g., `src/app/<category>/<slug>/page.tsx`):

`import "@/content/adobe/<category>/<slug>.theme.css"; // Always import scoped theme CSS first
import { AdobePage } from "@/components/adobe/AdobePage";
import type { AdobePageSpec } from "@/components/adobe/AdobePage";
import spec from "@/content/adobe/<category>/<slug>.json";

export default function Page() {
  return <AdobePage spec={spec as AdobePageSpec} />;
}`

---

## 4. What It Produces

| Output Path | Purpose |
| :--- | :--- |
| `src/content/adobe/<category>/<slug>.json` | The ordered page JSON specification |
| `src/content/adobe/<category>/<slug>.theme.css` | Scoped theme CSS (`.adobe-theme-<category>-<slug>`) |
| `public/<category>/<slug>/images/*` | Every image downloaded locally from the page |
| `public/<category>/<slug>/theme/*` | Local assets referenced by built-in themes |

### Spec Shape

`{
  source: string;
  theme: string;
  fontKits: string[];
  title: string;
  sections: AdobeSection[];
  author?: string;
  credits?: string;
  runtime: "classic" | "new";
}`

* **`sections[]`** items contain: `kind` (`single-column`, `full-width`, `split`, `window`, `fullscreen`, `photo-grid`, `flipbook`, `spacer`), original class names, and `elements[]`.
* **`elements[]`** items contain: `h2`, `h3`, `h4`, `p`, `blockquote` (inline HTML preserved), `ul`, `ol`, `button`, `image`, `video`, and `raw` (a safe fallback container for unrecognized nodes so nothing is silently dropped).

TypeScript types can be referenced in `src/components/adobe/AdobePage.tsx`.

---

## 5. How It Renders

* **`AdobePage.tsx`**: Translates the JSON spec into markup mirroring Adobe's DOM hierarchy (`.section > .section-view > .section-content > .content-container`, `.image`, `.link-button-wrapper`, etc.) so the extracted theme CSS styles the elements identically. Dynamically injects Adobe Fonts kits.
* **`adobe-layout.css`**: Reproduces Adobe's structural runtime layouts (section stacking, split columns, photo-grid matrices). Built using `:where(.adobe-page)` to maintain minimal CSS specificity so theme styles always take precedence.
* **`RevealOnScroll.tsx`**: Optional lightweight helper replicating Adobe's viewport scroll fade-ins.
* **Runtime Quirks**: Older Spark pages (runtime 1.22) scale inline photos to match column width; modern pages (runtime 1.23+) preserve native aspect ratios. The extractor tags `runtime: "classic" | "new"` and sets `displayWidth` to ensure 1:1 visual fidelity.

---

## 6. Video Handling

Use `video_map.py` to route embedded video IDs:

* **Remapped:** Assign legacy IDs to an alternate CDN or custom player.
* **Third-Party:** Retains original embeds (e.g., standard YouTube or Vimeo URLs).
* **Unresolved / Placeholders:** Unmapped IDs generate an accessible placeholder container (`data-legacy-video="<id>"`) with deep-link anchors (`/<category>/<slug>#video-N`).

---

## 7. Network Requirements

**During Extraction Only:**
* `express.adobe.com` / `new.express.adobe.com` (scraping pages and downloading images)
* `page.adobespark-assets.com` (runtime stylesheets and theme assets)
* `use.typekit.net` (Adobe Typekit font kit bundles)

**At Runtime:** The site serves all HTML, JSON, CSS, and images locally. External network requests are only made for Adobe Typekit web fonts and any embedded third-party video iframes.

---

## 8. Known Limitations

* **Static Scraping:** Parses server-rendered and public DOM snapshots; client-side JS behaviors are recreated statically or via React components.
* **Flip-books:** Card flip-book sections are extracted as sequential full-screen bands rather than scroll-pinned canvas animations.
* **Photo Grids:** Grids render responsive CSS tiles; modal lightbox viewer is not included by default.
* **Footers:** Adobe platform footers (*Appreciate*, *Report Abuse*) are omitted.
* **Baked-In Typography:** Headings or typography baked directly into raster image assets on newer Express templates remain raster images.

---

## 9. Adding New Section or Layout Types

1. **Inspect:** Run `node scripts/adobe-extractor/checks/compare-to-live.cjs <live-url> <local-url>` to spot discrepancies. Identify target DOM classes in the original markup (e.g., `div.section.<kind>-section`).
2. **Extract:** Add a parsing branch to `PageExtractor.parse_sections` in `adobe_page_to_spec.py`. Utilize `elements_in()` for body content and `fetch_image()` for local downloads.
3. **Render:** Add the section key to `AdobeSection` in `AdobePage.tsx` and render its corresponding DOM structure. Add layout scaffolding rules to `adobe-layout.css` within `:where(.adobe-page)`.
4. **Verify:** Check diffs via `compare-to-live.cjs` and execute smoke tests using `checks/verify-pages.cjs <base-url>`.

---

## File Overview

| File | Description |
| :--- | :--- |
| `adobe_page_to_spec.py` | Main CLI extractor (HTML parser, asset downloader, spec generator) |
| `video_map.py` | Video routing map (CDN remapping, external embeds, fallback handling) |
| `page_routes.py` | Adobe Page ID to local path dictionary for URL rewriting |
| `manifest.json` | Batch extraction registry |
| `checks/compare-to-live.cjs` | Puppeteer visual & DOM parity audit script |
| `checks/verify-pages.cjs` | Smoke-test runner for local routes (missing images, broken embeds, CSS overflow) |
