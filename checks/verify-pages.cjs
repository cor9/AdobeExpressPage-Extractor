#!/usr/bin/env node
/**
 * Browser smoke test for every archived Adobe page the site serves.
 *
 *   node scripts/adobe-extractor/checks/verify-pages.cjs <base-url> [route ...]
 *
 * With no routes, it reads src/content/adobe/<course>/<slug>.json and checks each page
 * (a course's "index" page is served at /courses/<course>). For each page, at 1440px and 390px wide,
 * it scrolls the whole page and reports: HTTP status, images that failed to load, horizontal overflow,
 * console errors, failed local requests, and how many Bunny / YouTube / Vimeo embeds and
 * "Video coming soon" placeholders it found. Exit code is non-zero if any page fails.
 *
 * Run it against `npm run dev` or, better, `npm run build && npm start`.
 * Third-party video hosts and Adobe Fonts are blocked during the check so it is fast and
 * deterministic; it verifies the embeds are present with the right source, not that they play.
 * Needs Playwright + Chromium (see compare-to-live.cjs for CHROMIUM_PATH / HTTPS_PROXY).
 */
// A sold course lives at a private address (see src/content/adobe/<course>/order.ts); others are under /courses/<course>.
function routeBase(course) {
  try {
    const order = require("fs").readFileSync(require("path").join(__dirname, "../../../src/content/adobe", course, "order.ts"), "utf8");
    const match = order.match(/PRIVATE_BASE = "([^"]+)"/);
    if (match) return match[1];
  } catch (error) {}
  return `/courses/${course}`;
}

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const { chromium } = require(execSync("npm root -g").toString().trim() + "/playwright");

const base = (process.argv[2] || "").replace(/\/$/, "");
if (!base) {
  console.error("usage: verify-pages.cjs <base-url> [route ...]");
  process.exit(2);
}

function routesFromContent() {
  const root = path.join(__dirname, "..", "..", "..", "src", "content", "adobe");
  const routes = [];
  for (const course of fs.readdirSync(root)) {
    const dir = path.join(root, course);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const file of fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort()) {
      const slug = file.replace(/\.json$/, "");
      routes.push(slug === "index" ? routeBase(course) : `${routeBase(course)}/${slug}`);
    }
  }
  return routes;
}

const routes = process.argv.length > 3 ? process.argv.slice(3) : routesFromContent();

function launchOptions() {
  const args = ["--ignore-certificate-errors"];
  if (process.env.HTTPS_PROXY) {
    args.push("--proxy-server=" + process.env.HTTPS_PROXY, "--proxy-bypass-list=<-loopback>;localhost;127.0.0.1");
  }
  return { executablePath: process.env.CHROMIUM_PATH || undefined, args };
}

(async () => {
  const browser = await chromium.launch(launchOptions());
  let allOk = true;
  for (const route of routes) {
    for (const [width, height] of [[1440, 900], [390, 800]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      await page.route(/(youtube\.com|mediadelivery\.net|vimeo\.com|typekit\.net)/, (r) => r.abort());
      const errors = [];
      const failed = [];
      page.on("console", (m) => {
        if (m.type() === "error" && !/webpack-hmr|WebSocket|net::ERR_/.test(m.text())) errors.push(m.text().slice(0, 140));
      });
      page.on("pageerror", (e) => errors.push("pageerror: " + e.message.slice(0, 140)));
      page.on("response", (r) => {
        if (r.status() >= 400 && r.url().startsWith(base)) failed.push(r.status() + " " + r.url().slice(-80));
      });
      const response = await page.goto(base + route, { waitUntil: "load", timeout: 120000 });
      const total = await page.evaluate(() => document.documentElement.scrollHeight);
      for (let y = 0; y < total; y += 700) {
        await page.evaluate((top) => window.scrollTo({ top, behavior: "instant" }), y);
        await page.waitForTimeout(110);
      }
      await page.waitForTimeout(3000);
      const info = await page.evaluate(() => {
        const images = [...document.querySelectorAll(".adobe-page img")];
        const frames = [...document.querySelectorAll(".adobe-page iframe")].map((i) => i.src);
        return {
          images: images.length,
          broken: images.filter((i) => !i.complete || i.naturalWidth === 0).length,
          bunny: frames.filter((s) => s.includes("mediadelivery.net/embed/")).length,
          youtube: frames.filter((s) => s.includes("youtube.com/embed/")).length,
          vimeo: frames.filter((s) => s.includes("player.vimeo.com")).length,
          placeholders: document.querySelectorAll(".video-placeholder").length,
          overflow: document.documentElement.scrollWidth > window.innerWidth,
        };
      });
      const ok = response.status() === 200 && info.broken === 0 && !info.overflow && errors.length === 0 && failed.length === 0;
      if (!ok) allOk = false;
      console.log(
        `${ok ? "OK  " : "FAIL"} ${route.padEnd(48)} ${String(width).padStart(4)}px  status ${response.status()}  images ${info.images} (broken ${info.broken})  ` +
          `bunny ${info.bunny} youtube ${info.youtube} vimeo ${info.vimeo} placeholders ${info.placeholders}  overflow ${info.overflow}  console errors ${errors.length}  bad responses ${failed.length}`,
        ...errors.slice(0, 2), ...failed.slice(0, 2),
      );
      await page.close();
    }
  }
  await browser.close();
  console.log(allOk ? "ALL PAGES OK" : "SOME FAILURES");
  process.exit(allOk ? 0 : 1);
})();
