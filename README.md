# AdobeExpressPage-Extractor

An archival tool that takes a public Adobe Express (Spark) page and turns it into a small, version-controlled JSON specification, plus local copies of its images and styling. This allows you to re-render the original page very closely in React without depending on Adobe's servers. It is ideal for preserving legacy content, restoring archived pages, or migrating off the platform.

1. What it does

For a given page, it records the following in original order:

⚬ Headings, paragraphs, lists, quotes (with inline bold/italic/links), buttons, and links.
⚬ Images with their display sizing, captions, and the copy Adobe stores in a figure's aria-label.
⚬ Video embeds in their exact positions (see §6).
⚬ Section types: single column, full-width photo, split layout, window band, full-screen photo, photo grid, card flip-book, spacers, title section (background photo + title), author/credits.
⚬ The page's theme CSS (re-scoped so pages cannot collide), the Adobe Fonts it uses, and any assets its theme references.
⚬ Links to other archived pages, rewritten to local routes (page_routes.py).

The live page's markup is the source of truth. Nothing is rewritten or "improved".

2. Input

A public page URL on either Adobe host:

⚬ [https://express.adobe.com/page/](https://express.adobe.com/page/)<ID>/ (classic Spark pages)
⚬ [https://new.express.adobe.com/webpage/](https://new.express.adobe.com/webpage/)<ID> (newer Adobe Express webpages)

You also provide a category/folder name and a slug (the page name; use index for a hub page).
Prerequisites: Python 3, standard library only. It downloads the page itself; --html FILE uses a saved local copy instead.

3. Run it

From the repository root:

python3 scripts/adobe-extractor/adobe_page_to_spec.py \
  https://express.adobe.com/page/<ID>/ my-category my-page


Options:

⚬ --image-size 2560 (default; max pixel width of stored images, Adobe resizes server-side) or --image-size orig for original files.
⚬ --html FILE to process a local file.
⚬ To re-archive every page listed in manifest.json: python3 scripts/adobe-extractor/adobe_page_to_spec.py --manifest scripts/adobe-extractor/manifest.json.

Re-running is safe: images already stored are skipped and outputs are deterministic. Record each new page in manifest.json and add its Adobe page id to page_routes.py (so sibling pages link to it locally).

Then add the route (one small file per page, e.g., src/app/<category>/<slug>/page.tsx):

import "@/content/adobe/<category>/<slug>.theme.css";            // import the theme CSS first
import { AdobePage } from "@/components/adobe/AdobePage";
import type { AdobePageSpec } from "@/components/adobe/AdobePage";
import spec from "@/content/adobe/<category>/<slug>.json";

export default function Page() { 
  return <AdobePage spec={spec as AdobePageSpec} />; 
}


4. What it produces

Output	Purpose
src/content/adobe/<category>/<slug>.json	The ordered page spec
src/content/adobe/<category>/<slug>.theme.css	The page's theme CSS, scoped to .adobe-theme-<category>-<slug>
public/<category>/<slug>/images/*	Every image on the page
public/<category>/<slug>/theme/*	Assets referenced by the theme CSS (only for built-in themes)

Spec shape: { source, theme, fontKits[], title, sections[], author?, credits?, runtime }.
sections[] items have a kind (single-column, full-width, split, window, fullscreen, photo-grid, flipbook, spacer), the original classes, and elements[]. Element types: h2/h3/h4/p/blockquote (inline HTML), ul/ol, button, image, video, and raw (a safe fallback for anything the extractor does not recognise; nothing is silently dropped). The TypeScript types are in src/components/adobe/AdobePage.tsx.

5. How the site renders it

⚬ src/components/adobe/AdobePage.tsx turns a spec into markup that mirrors Adobe's own DOM (.section > .section-view > .section-content > .content-container, .image, .link-button-wrapper, etc.), so the page's theme CSS applies unchanged. It also links the page's Adobe Fonts kits.
⚬ src/components/adobe/adobe-layout.css reproduces the parts of Adobe's runtime layout that the original page got from Adobe's JavaScript/runtime stylesheet (section stacking, split layout, photo-grid tile positions, etc.). It is deliberately written at the same low specificity as Adobe's runtime so each page's theme wins, as on the original.
⚬ RevealOnScroll.tsx re-creates the scroll fade-in.
⚬ Pages with an older Adobe runtime (1.22) scale inline images to the column; newer ones (1.23+, Adobe Express webpages) show them at their loaded size. The extractor records runtime: "classic" | "new" and displayWidth accordingly.

6. Video handling

If your original pages utilized specific video embeds, you can map them locally using video_map.py. This acts as a single place to decide how IDs are transformed:

⚬ Mapped: Rendered via a custom video player of your choice (e.g., mapping legacy Vimeo IDs to a new CDN).
⚬ Third-party: Preserved as-is (e.g., standard YouTube or active Vimeo embeds).
⚬ Unresolved: Replaced with a neutral gray "Video coming soon" box in the exact original position, keeping the legacy ID in the spec as data-legacy-video. Placeholders have an anchor: /<category>/<slug>#video-N jumps to the Nth video on the page.

To fill a placeholder, add its ID mapping to video_map.py and re-run the extractor. Nothing is guessed; unknown videos stay placeholders.

7. Network access needed

Only when extracting (the finished site serves everything locally except fonts and videos):

⚬ express.adobe.com, new.express.adobe.com (the pages and their images)
⚬ page.adobespark-assets.com (runtime/theme CSS and font scripts for classic pages)
⚬ use.typekit.net (Adobe Fonts kit CSS and font files, also loaded by the site at runtime)

At runtime, the site additionally embeds whichever video CDNs you authorize. In a locked-down environment, these hosts must be allowed or the visual checks cannot see them.

8. Known limitations

⚬ It archives what the public page serves. It does not render the page in a browser; behaviour Adobe produces with JavaScript is re-implemented by hand in adobe-layout.css / AdobePage.tsx.
⚬ Card flip-book sections (cards that advance over a pinned photo as you scroll) are rendered as one full-screen band per card, in order, not as a scroll-driven animation.
⚬ Photo grids are static (no lightbox); images open no large-preview viewer.
⚬ Adobe's footer ("Appreciate", Terms, Report Abuse) is intentionally dropped.
⚬ Section types it has not seen (pull quotes, glideshows, other layouts) are skipped at the section level; unknown elements inside known sections are kept as raw. Run checks/compare-to-live.cjs to find out.
⚬ Themes depend on Adobe Fonts kits that Adobe can change or retire; the site links them rather than storing font files.
⚬ Copy that Adobe stored only as image text (common on newer Express pages) stays image text.
⚬ Mobile layout comes from the page's own theme CSS (plus the split-layout stacking rules); ensure you test your extracted output on smaller viewports.

9. Adding support for a new section or layout type

1. Find it: Re-run the extractor and open the page. Compare with the original using node scripts/adobe-extractor/checks/compare-to-live.cjs <live-url> <local-url>; missing or mis-sized content points at it. In the original HTML, the section is a div.section.<kind>-section inside div.article.
2. Extract it: In adobe_page_to_spec.py, add a branch in PageExtractor.parse_sections that records the section's kind, classes, and its content in the spec. Use elements_in(container) for ordinary content, background(section) for a background photo, and fetch_image for any image so it is stored locally.
3. Render it: In AdobePage.tsx, add the kind to the AdobeSection type and a branch in the section loop that emits Adobe's own class names. If the original relied on Adobe's runtime for layout, copy the relevant rules from the page's runtime stylesheet into adobe-layout.css, wrapped in :where(.adobe-page) so they stay lower-specificity than page themes.
4. Verify: Run compare-to-live.cjs (aim for element diffs: 0) and checks/verify-pages.cjs <base-url>.

Files

File	Role
adobe_page_to_spec.py	The main extractor script
video_map.py	Maps legacy video IDs to new CDNs, third-party embeds, or placeholders
page_routes.py	Maps Adobe page IDs to local routes for internal linking
manifest.json	Registry of pages archived so far (re-run them all with --manifest)
checks/compare-to-live.cjs	Measures a recreated page against the live original
checks/verify-pages.cjs	Browser smoke test of every archived page (images, console, overflow, embeds)
