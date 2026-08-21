# 🎨 DESIGN.md (Visual Identity & Design System)
**Project:** KP Bromo Hub (FaceID-KP)

This document serves as the "Stitch" that holds our UI/UX together. Every new component, page, or modal must align with the design tokens defined here to maintain a cohesive, premium, and zero-bullshit aesthetic.

## 1. Core Aesthetic (The Vibe)
- **Glassmorphism:** Use semi-transparent backgrounds with backdrop-blur for overlays and navigation.
- **Dark Mode by Default:** The primary interface (kiosk and landing page) should lean towards deep, immersive dark tones to make the camera feed and colorful accents pop. Dashboard can utilize clean, bright dashboards for data legibility.
- **Subtle Micro-animations:** Buttons should scale on active states, hover effects should smoothly transition colors, and modals should gracefully fade/slide in.

## 2. Typography
We use modern, highly legible sans-serif fonts (e.g., *Inter*, *Plus Jakarta Sans*, or *Outfit*).
- **Headings (`h1`, `h2`, `h3`):** Bold to Extrabold (`font-bold`, `font-extrabold`). Tracking should be tight (`tracking-tight`).
- **Body (`p`, `span`):** Regular to Medium. Generous line height for readability (`leading-relaxed`).
- **Labels/Tags:** Tiny, uppercase, wide tracking (`text-[10px] uppercase font-bold tracking-wider text-slate-400`).

## 3. Color Palette (Tailwind Tokens)
Avoid generic red/green/blue. Use curated Tailwind hues.

### Primary Brand (The Spirit)
- **Sky Blue:** `sky-500` to `sky-600`. Used for primary actions, links, and progress bars.
- **Emerald Green:** `emerald-500` to `emerald-600`. Used for Success states, attendance streaks, and positive feedback.
- **Deep Slate (Backgrounds):** `slate-900` to `slate-950`. Used for main dark backgrounds. `slate-800` for cards/panels.

### Accent & Warning
- **Amber/Orange:** `orange-400` or `amber-500`. Used for warnings (e.g., Geofence out of range).
- **Rose/Red:** `red-500` or `rose-600`. Used for destructive actions (e.g., Delete Log).

## 4. UI Components ("The Stitches")

### Cards & Containers
- **Dark Panels:** `bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl`
- **Light Panels (Dashboard):** `bg-white p-6 rounded-2xl shadow-sm border border-slate-200`
- **Glass Overlays:** `bg-slate-950/80 backdrop-blur-md`

### Buttons
- **Primary Action (Register/Submit):** `bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 px-6 rounded-xl transition-transform active:scale-95 shadow-lg shadow-sky-900/50`
- **Secondary Action (Dashboard/Outline):** `bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 rounded-xl px-4 py-2 transition-colors`

### Feedback & Alerts
- Success markers should utilize circular backgrounds: `w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center border border-emerald-500/50`.

## 5. Implementation Rules
1. **Never use raw CSS if Tailwind can do it.** (Exceptions: complex custom keyframe animations like the countdown bar).
2. **Interactive elements must feel alive.** Always include `hover:` and `transition-all` classes.
3. **Consistency is mandatory.** Don't invent new padding sizes or border radii. Stick to `p-4`, `p-6`, `p-8` and `rounded-xl`, `rounded-2xl`, `rounded-3xl`.
