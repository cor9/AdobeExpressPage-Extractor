#!/usr/bin/env python3
"""Archive a public Adobe Express (Spark) page as a JSON page spec, theme CSS and local assets.

Usage:
  python3 scripts/adobe-extractor/adobe_page_to_spec.py <page-url> <course> <slug> [--image-size 2560|orig] [--html FILE]
  python3 scripts/adobe-extractor/adobe_page_to_spec.py --manifest scripts/adobe-extractor/manifest.json

Writes (paths relative to the repository root):
  src/content/adobe/<course>/<slug>.json        ordered page spec (sections -> elements)
  src/content/adobe/<course>/<slug>.theme.css   the page's theme CSS, re-scoped to
                                                .adobe-theme-<course>-<slug> so pages cannot collide
  public/courses/<course>/<slug>/images/*       every image on the page, stored locally
  public/courses/<course>/<slug>/theme/*        assets referenced by the theme CSS (if any)

The live page's markup is the source of truth: element order, headings, copy, links, buttons, images,
captions, video positions and section types are recorded exactly as published. See README.md in this
folder for the spec format, video handling, supported section types and known limitations.

Code layout (top to bottom): HTTP helpers, a tiny HTML tree, link/text helpers, then the
PageExtractor class (images -> videos -> elements -> sections -> theme CSS -> fonts -> output).
"""
import argparse
import gzip
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from page_routes import PAGE_ROUTES
from video_map import VIMEO_MAP, YOUTUBE_REPLACEMENTS, vimeo_title

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_AGENT = {"User-Agent": "Mozilla/5.0"}

# Adobe Fonts kit that every page's chrome (credits/author blocks) loads: adobe-clean + proxima-nova.
BASE_FONT_KIT = "onz5gap"
# CSS font names that are never Adobe Fonts kits.
GENERIC_FONTS = {"sans-serif", "serif", "inherit", "initial", "monospace", "helvetica", "arial"}


# ----------------------------------------------------------------------------------------------
# HTTP helpers
# ----------------------------------------------------------------------------------------------
def http_get(url):
    """Return (body bytes, content type) for a URL."""
    request = urllib.request.Request(url, headers=USER_AGENT)
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read(), response.headers.get("Content-Type", "")


def fetch_text(url):
    """Fetch a text resource; Adobe serves its runtime assets gzipped."""
    data, _ = http_get(url)
    return (gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data).decode("utf-8", "replace")


# ----------------------------------------------------------------------------------------------
# A tiny HTML tree (the standard library parser gives events, not a tree)
# ----------------------------------------------------------------------------------------------
class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def cls(self):
        return self.attrs.get("class", "").split()


VOID_TAGS = {"br", "img", "meta", "link", "input", "hr"}


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = Node("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID_TAGS:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)

    def handle_entityref(self, name):
        self.cur.children.append(f"&{name};")

    def handle_charref(self, name):
        self.cur.children.append(f"&#{name};")


def walk(node):
    """Depth-first iteration over a node and all its descendant nodes."""
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from walk(child)


def find_all(node, tag=None, css_class=None):
    return [n for n in walk(node) if (tag is None or n.tag == tag) and (css_class is None or css_class in n.cls())]


def find_first(node, tag=None, css_class=None):
    return next(iter(find_all(node, tag, css_class)), None)


# ----------------------------------------------------------------------------------------------
# Links and text
# ----------------------------------------------------------------------------------------------
INLINE_TAGS = ("b", "strong", "i", "em", "u", "br", "a", "span", "sup", "sub")


def local_href(href):
    """Map a link to another archived Adobe page onto its local route. Returns (target, is_internal)."""
    match = re.match(r"https?://(?:express|spark|new\.express)\.adobe\.com/(?:page|webpage)/([A-Za-z0-9]+)/?$", href or "")
    if match and match.group(1) in PAGE_ROUTES:
        return PAGE_ROUTES[match.group(1)], True
    return href, False


def inner_html(node):
    """Inner HTML of a node, keeping only inline formatting (b/i/u/a/br/...); everything else is unwrapped."""
    out = []
    for child in node.children:
        if isinstance(child, str):
            out.append(child)
        elif child.tag in INLINE_TAGS:
            if child.tag == "br":
                out.append("<br>")
                continue
            attrs = ""
            if child.tag == "a":
                target, internal = local_href(html.unescape(child.attrs.get("href", "")))
                attrs = f' href="{html.escape(target, quote=True)}"' + ("" if internal else ' target="_blank" rel="noopener noreferrer"')
            out.append(f"<{child.tag}{attrs}>{inner_html(child)}</{child.tag}>")
        else:
            out.append(inner_html(child))
    return "".join(out)


def text_of(node):
    return html.unescape(re.sub(r"<[^>]+>", "", inner_html(node))).strip()


def spacing_of(classes):
    """Adobe's large-content-spacing-top/bottom section classes."""
    return {
        "top": "large" if "large-content-spacing-top" in classes else "normal",
        "bottom": "large" if "large-content-spacing-bottom" in classes else "normal",
    }


def int_attr(node, name):
    return int(node.attrs.get(name, 0))


# ----------------------------------------------------------------------------------------------
# The extractor
# ----------------------------------------------------------------------------------------------
class PageExtractor:
    def __init__(self, raw_html, page_url, course, slug, image_size="2560"):
        self.raw = raw_html
        self.source_url = page_url  # recorded in the spec exactly as given
        # Relative image URLs resolve against the page URL (classic pages need a trailing slash).
        self.page_url = page_url if page_url.endswith("/") or "/webpage/" in page_url else page_url + "/"
        self.course, self.slug, self.image_size = course, slug, image_size

        self.scope = f"adobe-theme-{course}-{slug}"
        self.spec_path = os.path.join(REPO_ROOT, "src", "content", "adobe", course, f"{slug}.json")
        self.css_path = os.path.join(REPO_ROOT, "src", "content", "adobe", course, f"{slug}.theme.css")
        self.image_dir = os.path.join(REPO_ROOT, "public", "courses", course, slug, "images")
        self.theme_asset_dir = os.path.join(REPO_ROOT, "public", "courses", course, slug, "theme")
        self.public_images = f"/courses/{course}/{slug}/images"
        self.public_theme = f"/courses/{course}/{slug}/theme"
        os.makedirs(os.path.dirname(self.spec_path), exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)

        # Runtime generation. Adobe Express webpages and runtime >= 1.23 size inline images to the
        # loaded variant (size=N cap, shown inline-block); runtime 1.22 scales them to the column width.
        version = re.search(r"page\.adobespark-assets\.com/runtime/([0-9]+\.[0-9]+)", raw_html)
        self.express_webpage = "/webpage/static/runtime/" in raw_html
        self.new_runtime = self.express_webpage or bool(version and float(version.group(1)) >= 1.23)
        self.runtime_base = self._runtime_base()

        self.seen_images = {}
        self.theme_class = None

    # -- runtime location -----------------------------------------------------------------------
    def _runtime_base(self):
        if self.express_webpage:
            return "https://new.express.adobe.com/webpage/static/runtime"
        match = re.search(r"page\.adobespark-assets\.com/runtime/([0-9.]+)/", self.raw)
        return f"https://page.adobespark-assets.com/runtime/{match.group(1) if match else '1.22'}"

    # -- images ---------------------------------------------------------------------------------
    def _image_download_url(self, href):
        """URL to download an image from: the original, or capped to --image-size when Adobe allows it."""
        absolute = urllib.parse.urljoin(self.page_url, html.unescape(href))
        parts = urllib.parse.urlsplit(absolute)
        query = urllib.parse.parse_qs(parts.query)
        keep = {}
        if "/resources/" in parts.path and "asset_id" in query:
            keep["asset_id"] = query["asset_id"][0]
        if self.image_size != "orig" and "/resources/" in parts.path:
            keep["size"] = self.image_size
        elif self.image_size != "orig" and "asset_id" in query:
            keep["asset_id"] = query["asset_id"][0]
            keep["size"] = self.image_size
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(keep), ""))

    @staticmethod
    def _extension_for(data):
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        if data[:3] == b"\xff\xd8\xff":
            return ".jpg"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return ".gif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        if b"<svg" in data[:300]:
            return ".svg"
        return ".bin"

    def fetch_image(self, href):
        """Download an image into public/courses/... (skipping files already stored); return its public path."""
        path_key = urllib.parse.urlsplit(urllib.parse.urljoin(self.page_url, html.unescape(href))).path
        if path_key in self.seen_images:
            return self.seen_images[path_key]
        base = os.path.basename(path_key)
        existing = [f for f in os.listdir(self.image_dir) if os.path.splitext(f)[0] == os.path.splitext(base)[0]]
        if existing:
            name = existing[0]
        else:
            data, _ = http_get(self._image_download_url(href))
            name = base if os.path.splitext(base)[1] else base + self._extension_for(data)
            with open(os.path.join(self.image_dir, name), "wb") as handle:
                handle.write(data)
        self.seen_images[path_key] = f"{self.public_images}/{name}"
        return self.seen_images[path_key]

    # -- videos ---------------------------------------------------------------------------------
    @staticmethod
    def video_from_iframe(src):
        """Classify an embed. Vimeo ids go through VIMEO_MAP; YouTube is kept; anything else is passed through."""
        match = re.search(r"player\.vimeo\.com/video/(\d+)", src)
        if match:
            vimeo_id = match.group(1)
            mapped = VIMEO_MAP.get(vimeo_id)
            video = {"type": "video", "provider": "vimeo", "id": vimeo_id}
            if mapped and mapped.get("kind") == "bunny":
                video["bunny"] = {"guid": mapped["guid"], "title": mapped.get("title"), "needsReview": bool(mapped.get("needsReview"))}
            elif mapped and mapped.get("kind") == "youtube":
                return {"type": "video", "provider": "youtube", "id": mapped["id"], "legacyVimeoId": vimeo_id}
            elif mapped and mapped.get("kind") == "vimeo":
                video["thirdParty"] = True
            else:
                video["missing"] = {"note": (mapped or {}).get("note") or f"No mapping recorded. Vimeo library title: {vimeo_title(vimeo_id)}", "candidates": (mapped or {}).get("candidates", [])}
            return video
        match = re.search(r"youtube(?:-nocookie)?\.com/embed/([\w-]+)", src)
        if match:
            return {"type": "video", "provider": "youtube", "id": YOUTUBE_REPLACEMENTS.get(match.group(1), match.group(1))}
        return {"type": "video", "provider": "other", "src": src}

    # -- elements inside a section's content container -----------------------------------------------
    def element(self, node):
        """Convert one child of a content container into a spec element (or None to skip it)."""
        tag, classes = node.tag, node.cls()
        align = "center" if "text-center" in classes else None

        if tag in ("h3", "h4", "p", "h2", "blockquote"):
            result = {"type": tag, "html": inner_html(node).strip()}
        elif tag in ("ul", "ol"):
            result = {"type": tag, "items": [inner_html(li).strip() for li in node.children if isinstance(li, Node) and li.tag == "li"]}
        elif tag == "div" and "link-button-wrapper" in classes:
            return self._video_or_button(node, classes)
        elif tag in ("div", "figure") and "image" in classes:
            return self._image_element(node, tag)
        elif tag == "div" and ("author-appreciation-container" in classes or "photo-credits" in classes):
            return None  # handled by the dedicated author / credits sections
        else:
            # Anything unforeseen is kept verbatim (sanitised) rather than dropped.
            return {"type": "raw", "tag": tag, "class": " ".join(classes), "html": inner_html(node).strip()}

        if align:
            result["align"] = align
        return result

    def _video_or_button(self, node, classes):
        iframe = find_first(node, "iframe")
        alignment = "center" if "link-center" in classes else "left"
        if iframe:
            video = self.video_from_iframe(iframe.attrs.get("src", ""))
            video["align"] = alignment
            return video
        link = find_first(node, "a")
        target, internal = local_href(html.unescape(link.attrs.get("href", "")))
        button = {"type": "button", "label": text_of(link), "href": target, "align": alignment}
        if internal:
            button["internal"] = True
        return button

    def _image_element(self, node, tag):
        placeholder = find_first(node, css_class="image-placeholder-link")
        caption = find_first(node, css_class="caption")
        href = placeholder.attrs.get("data-href") if placeholder else None
        image = {
            "type": "image",
            "src": self.fetch_image(href),
            "width": int_attr(placeholder, "data-image-width"),
            "height": int_attr(placeholder, "data-image-height"),
        }
        # Newer runtimes load inline images at the placeholder's size=N variant (longest side <= N) and show
        # them at that natural size, so a 1080x1920 portrait with size=1024 displays 576px wide.
        size = re.search(r"[?&]size=(\d+)", html.unescape(href or ""))
        if self.new_runtime and size and max(image["width"], image["height"]) > int(size.group(1)):
            image["displayWidth"] = round(image["width"] * int(size.group(1)) / max(image["width"], image["height"]))
        if tag == "figure":
            image["figure"] = True
            if node.attrs.get("aria-label"):
                image["label"] = html.unescape(node.attrs["aria-label"])
        if caption:
            image["caption"] = inner_html(caption).strip()
        return image

    def elements_in(self, container):
        return [e for e in (self.element(child) for child in container.children if isinstance(child, Node)) if e]

    # -- backgrounds ----------------------------------------------------------------------------------
    def _background(self, link, holder):
        position = re.search(r"background-position:\s*([^;]+)", holder.attrs.get("style", "") if holder else "")
        return {
            "image": self.fetch_image(link.attrs["href"]),
            "width": int_attr(link, "data-image-width"),
            "height": int_attr(link, "data-image-height"),
            "position": position.group(1).strip() if position else "50% 50%",
        }

    def background(self, section):
        link = find_first(section, css_class="background-image-placeholder-link")
        if not link:
            return None
        return self._background(link, find_first(section, css_class="section-background-image"))

    # -- sections -------------------------------------------------------------------------------------
    def parse_sections(self, article, result):
        """Walk the article's top-level sections in order, filling result["title"/"sections"/"author"/"credits"].

        To support a new Adobe section type, add a branch here and a matching renderer in
        src/components/adobe/AdobePage.tsx (see README.md, "Adding a new section type").
        """
        for section in article.children:
            if not isinstance(section, Node) or "section" not in section.cls():
                continue
            classes = section.cls()
            rest = classes[1:]  # every class after "section", kept so the theme CSS can still match

            if "title-section" in classes:
                result["title"] = self._title_section(section, classes)
            elif "spacer-section" in classes:
                result["sections"].append({"kind": "spacer", "classes": rest, "elements": []})
            elif "fullscreen-photo-section" in classes:
                result["sections"].append({"kind": "fullscreen", "classes": rest, "background": self.background(section), "elements": []})
            elif "photo-grid-section" in classes:
                result["sections"].append(self._photo_grid_section(section, classes))
            elif "card-flipbook-section" in classes:
                result["sections"].append(self._flipbook_section(section, classes))
            elif "window-section" in classes:
                result["sections"].append({"kind": "window", "classes": rest, "background": self.background(section), "elements": []})
            elif "single-column-section" in classes or "full-width-section" in classes:
                result["sections"].append(self._column_section(section, classes))
            elif "author-section" in classes:
                name = find_first(section, css_class="name")
                if name:
                    result["author"] = text_of(name)
            elif "credits-section" in classes:
                result["credits"] = [text_of(p) for p in find_all(section, "p") if "credits-label" not in p.cls()]
            # The bumper/footer ("Terms of Service", "Report Abuse") is Adobe chrome and is intentionally dropped.

    def _title_section(self, section, classes):
        background = self.background(section)
        title = next(x for x in walk(section) if "title" in x.cls() and x.tag == "span")
        subtitle = find_first(section, css_class="subtitle") or Node("span", {}, None)
        return {
            "position": next((c for c in classes if c.startswith("title-") and c != "title-section"), "title-center"),
            "title": text_of(title),
            "subtitle": text_of(subtitle),
            "image": background["image"],
            "imageWidth": background["width"],
            "imageHeight": background["height"],
            "backgroundPosition": background["position"],
        }

    def _column_section(self, section, classes):
        container = find_first(section, css_class="content-container")
        kind = "full-width" if "full-width-section" in classes else ("split" if "split-layout" in classes else "single-column")
        entry = {"kind": kind, "classes": classes[1:], "spacing": spacing_of(classes), "elements": self.elements_in(container)}
        if kind == "split":
            entry["background"] = self.background(section)
        return entry

    def _photo_grid_section(self, section, classes):
        grid = []
        for group in (x for x in walk(section) if "photo-group" in x.cls() and x.tag == "div"):
            tiles = []
            for tile in find_all(group, css_class="photo-image"):
                href = tile.attrs.get("data-src") or tile.attrs.get("href")
                tiles.append({"src": self.fetch_image(href), "width": int_attr(tile, "data-image-width"), "height": int_attr(tile, "data-image-height")})
            layout = next((c for c in group.cls() if re.match(r"t\d-layout-", c)), "")
            grid.append({"layout": layout, "tiles": tiles})
        return {"kind": "photo-grid", "classes": classes[1:], "spacing": spacing_of(classes), "grid": grid, "elements": []}

    def _flipbook_section(self, section, classes):
        backgrounds = []
        for holder in find_all(section, css_class="section-background-image"):
            link = find_first(holder, css_class="background-image-placeholder-link")
            if link:
                backgrounds.append(self._background(link, holder))
        cards = []
        for view in find_all(section, css_class="section-content-view"):
            container = find_first(view, css_class="content-container")
            if container:
                cards.append({"classes": [c for c in view.cls() if c != "section-content-view"], "elements": self.elements_in(container)})
        return {"kind": "flipbook", "classes": classes[1:], "backgrounds": backgrounds, "cards": cards, "elements": []}

    # -- theme CSS ------------------------------------------------------------------------------------
    def _localize_css_assets(self, css, base_url):
        """Store relative url(...) assets (e.g. a theme's quote mark) locally so nothing depends on Adobe."""

        def swap(match):
            quote, ref = match.group(1), match.group(2).strip()
            if ref.startswith(("data:", "http:", "https:", "/", "#")):
                return match.group(0)
            absolute = urllib.parse.urljoin(base_url, ref)
            os.makedirs(self.theme_asset_dir, exist_ok=True)
            name = os.path.basename(urllib.parse.urlsplit(absolute).path)
            destination = os.path.join(self.theme_asset_dir, name)
            if not os.path.exists(destination):
                data, _ = http_get(absolute)
                with open(destination, "wb") as handle:
                    handle.write(data)
            return f"url({quote}{self.public_theme}/{name}{quote})"

        return re.sub(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", swap, css)

    def build_theme_css(self):
        """Adobe's built-in themes (luca, crisp, ...) ship as external stylesheets; custom themes are
        inlined in the page. The external sheet loads first and the inline <style> overrides it. Every
        selector is re-scoped from the page's theme class to this page's unique scope class."""
        external = []
        for href in re.findall(r'<link[^>]+href="([^"]*/themes/[^"]+\.css)"', self.raw):
            href = urllib.parse.urljoin(self.source_url, href.replace("&amp;", "&"))
            external.append(self._localize_css_assets(fetch_text(href), href))
        inline = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", self.raw, flags=re.S))
        style = "\n".join(external + [inline])
        style = re.sub(r"\.%s\b" % re.escape(self.theme_class), "." + self.scope, style)
        with open(self.css_path, "w", encoding="utf-8") as handle:
            handle.write(f"/* Theme CSS from {self.source_url} (theme class {self.theme_class}, re-scoped to .{self.scope}). */\n{style.strip()}\n")
        return style

    # -- Adobe Fonts ----------------------------------------------------------------------------------
    def resolve_font_kits(self, style):
        """Return (kit stylesheet URLs, resolved family labels).

        The page loads its Adobe Fonts kits through small scripts (base-fonts, themes/<theme>-fonts,
        font-subgroup-kits/<family>); each script names the kit ids it pulls in. Font names found in the
        theme CSS are also tried as subgroup kits for families the scripts do not cover."""
        kits, resolved = [], []

        scripts = re.findall(r'src="([^"]*(?:-fonts|font-subgroup-kits/[a-z0-9-]+)\.gz\.js)"', self.raw)
        # Built-in themes are linked as themes/<name>.gz.css; the runtime loads themes/<name>-fonts.gz.js for them.
        scripts += [re.sub(r"\.gz\.css$", "-fonts.gz.js", h) for h in re.findall(r'<link[^>]+href="([^"]*/themes/[^"]+\.gz\.css)"', self.raw)]
        for src in dict.fromkeys(scripts):
            try:
                found = re.findall(r"typekit\.net/([a-z0-9]{7})", fetch_text(urllib.parse.urljoin(self.source_url, src)))
            except Exception:  # noqa: BLE001 - a missing optional script just means no extra fonts
                continue
            if found:
                kits += found
                resolved.append(os.path.basename(src).replace(".gz.js", ""))

        names = set()
        for group in re.findall(r"font-family:\s*([^;}]+)", style):
            for family in group.split(","):
                family = family.strip().strip("\"'").lower()
                if re.fullmatch(r"[a-z0-9-]+", family) and family not in GENERIC_FONTS:
                    names.add(family)
        for family in sorted(names):
            try:
                found = re.findall(r"typekit\.net/([a-z0-9]{7})", fetch_text(f"{self.runtime_base}/font-subgroup-kits/{family}.gz.js"))
            except Exception:  # noqa: BLE001 - not every family has a subgroup kit (system fonts etc.)
                continue
            if found:
                kits += found
                resolved.append(family)

        urls = [f"https://use.typekit.net/{kit}.css" for kit in dict.fromkeys([BASE_FONT_KIT] + kits)]
        return urls, resolved

    # -- run -----------------------------------------------------------------------------------------
    def run(self):
        tree = TreeBuilder()
        tree.feed(self.raw)
        article = next(n for n in walk(tree.root) if "article" in n.cls() and "sections-article-layout" in n.cls())
        self.theme_class = next(c for c in article.cls() if c.endswith("-theme"))

        # Key order is part of the output format (the committed specs were generated in this order).
        result = {"source": self.source_url, "theme": self.scope, "fontKits": [], "title": None, "sections": []}
        self.parse_sections(article, result)

        style = self.build_theme_css()
        result["fontKits"], families = self.resolve_font_kits(style)
        result["runtime"] = "new" if self.new_runtime else "classic"

        with open(self.spec_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        videos = [e for s in result["sections"] for e in s["elements"] if e["type"] == "video"]
        print(
            f"{self.slug}: {len(result['sections'])} sections, {sum(len(s['elements']) for s in result['sections'])} elements, "
            f"{len(self.seen_images)} images, {len(videos)} videos (bunny {sum(1 for v in videos if 'bunny' in v)}, "
            f"missing {sum(1 for v in videos if 'missing' in v)}), fonts {families}"
        )
        return result


# ----------------------------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------------------------
def archive_page(url, course, slug, image_size="2560", html_file=None):
    raw = open(html_file, encoding="utf-8").read() if html_file else http_get(url)[0].decode("utf-8")
    return PageExtractor(raw, url, course, slug, image_size).run()


def main():
    parser = argparse.ArgumentParser(description="Archive public Adobe Express pages as page specs + local assets.")
    parser.add_argument("url", nargs="?", help="Adobe Express page URL (https://express.adobe.com/page/<ID>/ or https://new.express.adobe.com/webpage/<ID>)")
    parser.add_argument("course", nargs="?", help="course folder name, e.g. perfect-self-tape (also the /courses/<course>/ route)")
    parser.add_argument("slug", nargs="?", help="page name, e.g. equipment-guide (a course's hub page uses 'index')")
    parser.add_argument("--image-size", default="2560", help="'orig' for original image files, or a max pixel width (default 2560)")
    parser.add_argument("--html", help="use this saved copy of the page instead of downloading it")
    parser.add_argument("--manifest", help="archive every page listed in this JSON file (see manifest.json)")
    args = parser.parse_args()

    if args.manifest:
        with open(args.manifest, encoding="utf-8") as handle:
            for entry in json.load(handle):
                archive_page(entry["url"], entry["course"], entry["slug"], entry.get("imageSize", "2560"))
        return
    if not (args.url and args.course and args.slug):
        parser.error("give <url> <course> <slug>, or --manifest FILE")
    archive_page(args.url, args.course, args.slug, args.image_size, args.html)


if __name__ == "__main__":
    sys.exit(main())
