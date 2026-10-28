// Renders the README art in src/ to PNG with headless Chromium, in ArtCraft Launcher's own typefaces.
// Usage: python3 assets/extract.py && node assets/render.cjs [banner ...]   (needs the `playwright` package)
// The pages draw the suite from edition/suite.json and its icons from app-icons/; the fonts come from .deps/fonts/.
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join } = require('node:path');
const { pathToFileURL } = require('node:url');

const root = join(__dirname, '..');
const jobs = [
  { name: 'banner', width: 1280, height: 320, scale: 2 },
  { name: 'social-preview', width: 1280, height: 640, scale: 1 },
  { name: 'icon', width: 512, height: 512, scale: 1 },
];
const fonts = [
  ['Archivo', 'Archivo.ttf', 'font-weight: 100 900; font-stretch: 62% 125%;'],
  ['Inter', 'Inter.ttf', 'font-weight: 100 900;'],
  ['Geist Mono', 'GeistMono.ttf', 'font-weight: 100 900;'],
];

function fontFaces() {
  return fonts.map(([family, file, axes]) => {
    const path = join(root, '.deps', 'fonts', file);
    if (!existsSync(path)) throw new Error(`${path} is missing: run python3 assets/extract.py`);
    const data = readFileSync(path).toString('base64');
    return `@font-face { font-family: '${family}'; src: url(data:font/ttf;base64,${data}) format('truetype'); ${axes} }`;
  }).join('\n');
}

// What every page gets before its own script runs: the suite, and how to draw an app's icon and name.
function prelude(apps) {
  return `window.SUITE = ${JSON.stringify(apps)};
    window.icon = (app) => Object.assign(document.createElement('img'), { src: '../app-icons/' + app.id + '.png', alt: app.name });
    window.appName = (app) => {
      const div = document.createElement('div');
      div.className = 'name';
      div.style.setProperty('--c', app.color);
      div.append(app.name.replace(/Craft$/, ''));
      div.appendChild(document.createElement('b')).textContent = 'Craft';
      return div;
    };`;
}

(async () => {
  const only = process.argv.slice(2);
  const apps = JSON.parse(readFileSync(join(root, 'edition', 'suite.json'), 'utf8')).apps;
  const faces = fontFaces();
  const browser = await chromium.launch();
  for (const job of jobs.filter((j) => !only.length || only.includes(j.name))) {
    const page = await browser.newPage({ viewport: { width: job.width, height: job.height }, deviceScaleFactor: job.scale });
    await page.addInitScript(prelude(apps));
    await page.goto(pathToFileURL(join(__dirname, 'src', `${job.name}.html`)).href);
    await page.addStyleTag({ content: faces });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map((image) => image.decode()));
    });
    const out = join(__dirname, `${job.name}.png`);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: job.width, height: job.height }, omitBackground: true });
    await page.close();
    console.log(`${job.name}.png (${job.width * job.scale}x${job.height * job.scale})`);
  }
  await browser.close();
})();
