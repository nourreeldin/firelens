import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import opentype from "opentype.js";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Flame } from "lucide-react";

const require = createRequire(import.meta.url);
const nextRequire = createRequire(require.resolve("next/package.json"));
const sharp = nextRequire("sharp");
const publicDir = new URL("../public/", import.meta.url);

// Match the dashboard's 32px brand mark, including its Lucide flame.
function iconSvg(dark = false, adaptive = false) {
  const palette = dark
    ? { fill: "#1f1309", border: "#3d2206", flame: "#d47535" }
    : { fill: "#fff4eb", border: "#f5d4b3", flame: "#b35d27" };
  const flame = renderToStaticMarkup(createElement(Flame, {
    x: 15, y: 15, width: 34, height: 34, color: palette.flame,
    strokeWidth: 2, className: "flame",
  }));
  return `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" role="img" aria-label="FireLens">
  <title>FireLens</title>
  ${adaptive ? '<style>@media(prefers-color-scheme:dark){.background{fill:#1f1309;stroke:#3d2206}.flame{stroke:#d47535}}</style>' : ""}
  <rect class="background" x="1" y="1" width="62" height="62" rx="13" fill="${palette.fill}" stroke="${palette.border}" stroke-width="2"/>
  ${flame}
</svg>\n`;
}

await writeFile(new URL("icon.svg", publicDir), iconSvg(false, true));
await writeFile(new URL("firelens-logo.svg", publicDir), iconSvg());
// Outline the sidebar's Windows system font so SVG/PNG consumers do not
// substitute a different face. Other systems can supply the two font paths.
const fontDirectory = join(process.env.WINDIR || "C:/Windows", "Fonts");
async function loadFont(filename) {
  const bytes = await readFile(filename);
  return opentype.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
}
const [bold, semibold] = await Promise.all([
  loadFont(process.env.FIRELENS_LOGO_BOLD_FONT || join(fontDirectory, "segoeuib.ttf")),
  loadFont(process.env.FIRELENS_LOGO_SEMIBOLD_FONT || join(fontDirectory, "seguisb.ttf")),
]);
const letters = bold.getPaths("firelens", 80, 35, 37.333, { kerning: true, letterSpacing: -1.0667 / 37.333 });
const tagline = semibold.getPath("EARTH OBSERVATION", 81, 57, 12.444, { kerning: true, letterSpacing: 2.6667 / 12.444 });
const wordmarkWidth = Math.ceil(Math.max(236, tagline.getBoundingBox().x2, ...letters.map((path) => path.getBoundingBox().x2)) + 4);
const outline = (path) => `<path d="${path.toPathData(3)}"/>`;
const wordmarkSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="${wordmarkWidth}" height="64" viewBox="0 0 ${wordmarkWidth} 64" role="img" aria-label="FireLens — Earth observation">
  <title>FireLens — Earth observation</title>
  ${iconSvg()}
  <g fill="#12253c">${letters.slice(0, 4).map(outline).join("")}</g>
  <g fill="#b35d27">${letters.slice(4).map(outline).join("")}</g>
  <g fill="#8899ac">${outline(tagline)}</g>
</svg>\n`;
await writeFile(new URL("firelens-wordmark.svg", publicDir), wordmarkSvg);
await sharp(Buffer.from(wordmarkSvg)).resize(wordmarkWidth * 4, 256).png().toFile(fileURLToPath(new URL("firelens-wordmark.png", publicDir)));
console.log(`Generated firelens-wordmark.svg and firelens-wordmark.png (${wordmarkWidth * 4} × 256)`);
for (const [filename, size, dark] of [
  ["icon-light-32x32.png", 32, false],
  ["icon-dark-32x32.png", 32, true],
  ["apple-icon.png", 180, false],
  ["firelens-logo.png", 512, false],
]) {
  await sharp(Buffer.from(iconSvg(dark))).resize(size, size).png().toFile(fileURLToPath(new URL(filename, publicDir)));
  console.log(`Generated ${filename} (${size} × ${size})`);
}
