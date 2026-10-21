#!/usr/bin/env node
/**
 * Compare a recreated page with its live Adobe Express original.
 *
 *   node scripts/adobe-extractor/checks/compare-to-live.cjs <live-url> <local-url> [width=1440]
 *
 * Loads both pages in headless Chromium and compares every heading, paragraph, list, quote, image,
 * video box, button, caption and photo tile in document order: position (x), size (w/h), font size and
 * (for text) font family. Prints "element diffs: 0" when the recreation matches. Differences smaller
 * than a few pixels are ignored.
 *
 * Needs Playwright (resolved from the global npm root) and Chromium. Environment:
 *   CHROMIUM_PATH  path to a Chromium binary, if Playwright's own browser is not installed
 *   HTTPS_PROXY    used automatically when set
 *   BLOCK_TYPEKIT=1  stop the *local* page from loading Adobe Fonts. Useful when Adobe's own page does
 *                    not load its web fonts in your environment, so both sides render with fallbacks.
 * Note: live Adobe pages reveal images/captions with a scroll animation; this script removes the
 * "hidden" state before measuring so positions are comparable.
 */
const { execSync } = require("child_process");
const { chromium } = require(execSync("npm root -g").toString().trim() + "/playwright");

const [, , liveUrl, localUrl, width = "1440"] = process.argv;
if (!liveUrl || !localUrl) {
  console.error("usage: compare-to-live.cjs <live-url> <local-url> [width]");
  process.exit(2);
}

const SELECTOR = [
  ".title-section .title", ".content-container h3", ".content-container h4", ".content-container p",
  ".content-container ul", ".content-container ol", ".content-container blockquote", ".image-wrapper",
  ".embedded-link-wrapper", "a.link-button", ".caption", ".photo-container",
].join(", ");

function launchOptions() {
  const args = ["--ignore-certificate-errors"];
  if (process.env.HTTPS_PROXY) {
    args.push("--proxy-server=" + process.env.HTTPS_PROXY, "--proxy-bypass-list=<-loopback>;localhost;127.0.0.1");
  }
  return { executablePath: process.env.CHROMIUM_PATH || undefined, args };
}

async function measure(browser, url, isLive) {
  const page = await browser.newPage({ viewport: { width: Number(width), height: 900 } });
  if (!isLive && process.env.BLOCK_TYPEKIT) await page.route(/typekit\.net/, (route) => route.abort());
  await page.goto(url, { waitUntil: "networkidle", timeout: 90000 }).catch((error) => console.log("goto:", error.message));
  await page.waitForTimeout(isLive ? 5000 : 2500);
  if (!isLive) {
    // Scroll through so lazy images load and the reveal animation runs.
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    for (let y = 0; y < height; y += 900) {
      await page.evaluate((top) => window.scrollTo({ top, behavior: "instant" }), y);
      await page.waitForTimeout(80);
    }
    await page.waitForTimeout(1500);
  }
  const elements = await page.evaluate((selector) => {
    document.querySelectorAll(".hidden,.adobe-reveal-hidden").forEach((el) => el.classList.remove("hidden", "adobe-reveal-hidden"));
    const style = document.createElement("style");
    style.textContent = "*{transition:none!important}";
    document.head.appendChild(style);
    return [...document.querySelectorAll(selector)].map((el) => {
      const rect = el.getBoundingClientRect();
      const css = getComputedStyle(el);
      return {
        tag: el.tagName + "." + String(el.className || "").split(" ")[0],
        x: Math.round(rect.left), w: Math.round(rect.width), h: Math.round(rect.height),
        fontSize: css.fontSize, fontFamily: css.fontFamily.split(",")[0].replace(/"/g, "").slice(0, 20),
        text: (el.textContent || "").trim().slice(0, 20),
      };
    });
  }, SELECTOR);
  await page.close();
  return elements;
}

(async () => {
  const browser = await chromium.launch(launchOptions());
  const live = await measure(browser, liveUrl, true);
  const local = await measure(browser, localUrl, false);
  await browser.close();

  console.log(`[@${width}] elements: live ${live.length}, local ${local.length}`);
  let diffs = 0;
  for (let i = 0; i < Math.min(live.length, local.length); i += 1) {
    const a = live[i];
    const b = local[i];
    const notes = [];
    for (const key of ["x", "w", "h"]) if (Math.abs(a[key] - b[key]) > 3) notes.push(`${key}:${a[key]}->${b[key]}`);
    if (a.fontSize !== b.fontSize) notes.push(`fontSize:${a.fontSize}->${b.fontSize}`);
    // Font family is only meaningful on elements that contain text.
    if (a.fontFamily !== b.fontFamily && /^(H[2-4]|P|A|BLOCKQUOTE|SPAN|UL|OL)\./.test(a.tag)) notes.push(`font:${a.fontFamily}->${b.fontFamily}`);
    if (notes.length) {
      diffs += 1;
      if (diffs <= 15) console.log(`  #${i} ${a.tag} "${a.text}" | ${notes.join(", ")}`);
    }
  }
  console.log(`element diffs: ${diffs}`);
  process.exit(diffs === 0 && live.length === local.length ? 0 : 1);
})();
