#!/usr/bin/env node
/**
 * Fail if any page uses a Tailwind colour token that the shared theme does not
 * define.
 *
 * Tailwind silently generates nothing for an unknown colour, and this project
 * has no build step, so the failure is invisible: the kiosk used bg-azure-600
 * on its "Cari Nama Manual" and "Check-in" buttons while index.html defined no
 * azure palette at all. Those buttons rendered as bare text on a dark panel —
 * in the one screen where a member needs to find the fallback.
 *
 *   node scripts/check_theme_tokens.js
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const THEME = path.join(ROOT, 'frontend/js/tailwind-theme.js');
const TOKEN = /\b(?:bg|text|border|shadow|ring|from|via|to|decoration|outline|divide|accent|caret|fill|stroke)-(azure|obsidian)-(\d{2,3})/g;

global.window = {};
eval(fs.readFileSync(THEME, 'utf8'));

const palette = window.tailwind.config.theme.extend.colors;
const known = new Set();
for (const [name, shades] of Object.entries(palette)) {
  for (const shade of Object.keys(shades)) known.add(`${name}-${shade}`);
}

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['vendor', 'uploads', 'assets', 'node_modules'].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(html|js)$/.test(entry.name) && entry.name !== 'tailwind-theme.js') out.push(full);
  }
  return out;
}

const problems = [];
for (const file of walk(path.join(ROOT, 'frontend'))) {
  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split('\n');
  lines.forEach((line, index) => {
    for (const match of line.matchAll(TOKEN)) {
      const key = `${match[1]}-${match[2]}`;
      if (!known.has(key)) {
        problems.push(`${path.relative(ROOT, file)}:${index + 1}  ${match[0]}  (${key} is not in the shared theme)`);
      }
    }
  });
}

if (problems.length) {
  console.error('Undefined Tailwind colour tokens:\n');
  console.error(problems.join('\n'));
  console.error(`\n${problems.length} problem(s). Add the shade to frontend/js/tailwind-theme.js or use an existing one.`);
  process.exit(1);
}
console.log(`OK — every azure/obsidian token resolves against the shared theme (${known.size} shades defined).`);
