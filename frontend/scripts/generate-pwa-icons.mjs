/**
 * Generate branded PNG icons for PWA (no external deps).
 * Theme: sidebar blue #1e3a8a + accent #ef4444 (matches favicon.svg)
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, '..', 'public');

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
  }
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const typeBuf = Buffer.from(type, 'ascii');
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([len, typeBuf, data, crcBuf]);
}

function createPng(size, draw) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y++) {
    const rowStart = y * (size * 4 + 1);
    raw[rowStart] = 0;
    for (let x = 0; x < size; x++) {
      const [r, g, b, a = 255] = draw(x, y, size);
      const i = rowStart + 1 + x * 4;
      raw[i] = r;
      raw[i + 1] = g;
      raw[i + 2] = b;
      raw[i + 3] = a;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  const compressed = zlib.deflateSync(raw, { level: 9 });
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', compressed),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

function inRoundRect(x, y, size, radius) {
  const r = radius;
  if (x < 0 || y < 0 || x >= size || y >= size) return false;
  if (x >= r && x < size - r) return true;
  if (y >= r && y < size - r) return true;
  const corners = [
    [r, r],
    [size - 1 - r, r],
    [r, size - 1 - r],
    [size - 1 - r, size - 1 - r],
  ];
  for (const [cx, cy] of corners) {
    const dx = x - cx;
    const dy = y - cy;
    if (dx * dx + dy * dy <= r * r) return true;
  }
  return false;
}

function inCircle(x, y, cx, cy, radius) {
  const dx = x - cx;
  const dy = y - cy;
  return dx * dx + dy * dy <= radius * radius;
}

/** Thick stroke for letter shapes via filled rectangles */
function inRects(x, y, rects) {
  for (const [x0, y0, x1, y1] of rects) {
    if (x >= x0 && x <= x1 && y >= y0 && y <= y1) return true;
  }
  return false;
}

function drawIcon(x, y, size, { transparentOutside = true } = {}) {
  const radius = Math.round(size * 0.22);
  if (transparentOutside && !inRoundRect(x, y, size, radius)) {
    return [0, 0, 0, 0];
  }
  if (!transparentOutside && !inRoundRect(x, y, size, radius)) {
    return [0x1e, 0x3a, 0x8a, 255];
  }

  // Accent dot (top-right)
  if (inCircle(x, y, size * 0.78, size * 0.22, size * 0.075)) {
    return [0xef, 0x44, 0x44, 255];
  }

  // White "UJ" as block letters (normalized to 64x64 grid)
  const s = size / 64;
  const ux = (v) => Math.round(v * s);
  const uRects = [
    // U left stem
    [ux(14), ux(18), ux(18), ux(40)],
    // U right stem
    [ux(28), ux(18), ux(32), ux(40)],
    // U bottom curve (approx bars)
    [ux(14), ux(38), ux(32), ux(42)],
    // J top bar
    [ux(36), ux(18), ux(50), ux(22)],
    // J stem
    [ux(43), ux(18), ux(47), ux(40)],
    // J bottom hook
    [ux(36), ux(38), ux(47), ux(42)],
    [ux(36), ux(34), ux(40), ux(42)],
  ];
  if (inRects(x, y, uRects)) {
    return [255, 255, 255, 255];
  }

  return [0x1e, 0x3a, 0x8a, 255];
}

function drawMaskable(x, y, size) {
  // Full-bleed background for Android adaptive icons
  return drawIcon(x, y, size, { transparentOutside: false });
}

for (const size of [192, 512]) {
  fs.writeFileSync(path.join(outDir, `pwa-${size}.png`), createPng(size, (x, y, s) => drawIcon(x, y, s)));
  fs.writeFileSync(
    path.join(outDir, `pwa-${size}-maskable.png`),
    createPng(size, (x, y, s) => drawMaskable(x, y, s)),
  );
  console.log(`Wrote pwa-${size}.png (+ maskable)`);
}

fs.writeFileSync(
  path.join(outDir, 'apple-touch-icon.png'),
  createPng(180, (x, y, s) => drawIcon(x, y, s, { transparentOutside: false })),
);
console.log('Wrote apple-touch-icon.png');
