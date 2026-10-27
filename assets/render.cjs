// Renders the SVG sources in this folder to PNG with headless Chromium.
// Usage: node assets/render.cjs [banner.svg ...]   (needs the `playwright` package)
const { chromium } = require('playwright');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const jobs = [
  { src: 'banner.svg', out: 'banner.png', width: 1280, height: 400, scale: 1.5 },
  { src: 'social-preview.svg', out: 'social-preview.png', width: 1280, height: 640, scale: 1 },
  { src: 'icon.svg', out: 'icon.png', width: 512, height: 512, scale: 1 },
];

const only = process.argv.slice(2);

(async () => {
  const browser = await chromium.launch();
  for (const job of jobs.filter((j) => !only.length || only.includes(j.src))) {
    const page = await browser.newPage({
      viewport: { width: job.width, height: job.height },
      deviceScaleFactor: job.scale,
    });
    const svg = readFileSync(join(__dirname, job.src), 'utf8');
    await page.setContent(
      `<!doctype html><html><body style="margin:0;background:transparent">${svg}</body></html>`
    );
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: join(__dirname, job.out),
      clip: { x: 0, y: 0, width: job.width, height: job.height },
      omitBackground: true,
    });
    await page.close();
    console.log(`${job.src} -> ${job.out} (${job.width * job.scale}x${job.height * job.scale})`);
  }
  await browser.close();
})();
