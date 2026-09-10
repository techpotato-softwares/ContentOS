import sharp from "sharp"
import { writeFileSync } from "fs"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const publicDir = join(__dirname, "..", "public")

const teal = "#0d9488"
const ink = "#f0fdfa"
// Same mark as public/favicon.svg (viewBox 0 0 32)
const markPath =
  "M8 20V12h3.2c2.1 0 3.4 1.1 3.4 2.8 0 1.2-.7 2.1-1.8 2.5L16 20h-2.4l-2.5-2.5H10.4V20H8zm2.4-4.2h.8c.9 0 1.4-.4 1.4-1.1S11.1 13.6 10.2 13.6h-.8v2.2zM17.2 20l2.8-8h2.5l2.8 8h-2.5l-.4-1.3h-2.3L19.7 20h-2.5zm3.2-3.2h1.4l-.7-2.2-.7 2.2z"

function iconSvg(size, { maskable = false } = {}) {
  const pad = maskable ? size * 0.18 : 0
  const inner = size - pad * 2
  const rx = size * 0.22
  const s = inner / 32

  if (maskable) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" fill="${teal}"/>
  <g transform="translate(${pad},${pad}) scale(${s})">
    <path d="${markPath}" fill="${ink}"/>
  </g>
</svg>`
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${rx}" fill="${teal}"/>
  <g transform="scale(${s})">
    <path d="${markPath}" fill="${ink}"/>
  </g>
</svg>`
}

async function writePng(name, svg) {
  const file = join(publicDir, name)
  const buf = await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toBuffer()
  writeFileSync(file, buf)
  console.log(`${name}: ${buf.length} bytes`)
}

await writePng("pwa-192.png", iconSvg(192))
await writePng("pwa-512.png", iconSvg(512))
await writePng("pwa-512-maskable.png", iconSvg(512, { maskable: true }))
await writePng("apple-touch-icon.png", iconSvg(180))
console.log("PWA icons written to public/")
