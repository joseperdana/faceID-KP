---
name: Fluid Clarity
system: KP Bromo Web Digital Identity System
version: 2.0.0
colors:
  surface: '#0b0d13'
  surface-dim: '#06070a'
  surface-bright: '#11141e'
  surface-container-lowest: '#040507'
  surface-container-low: '#0e111a'
  surface-container: '#151926'
  surface-container-high: '#1c2233'
  surface-container-highest: '#242b40'
  on-surface: '#f8fafc'
  on-surface-variant: '#94a3b8'
  inverse-surface: '#f8fafc'
  inverse-on-surface: '#0f172a'
  outline: '#334155'
  outline-variant: 'rgba(255, 255, 255, 0.08)'
  surface-tint: '#3b82f6'
  primary: '#2563eb'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#dbeafe'
  inverse-primary: '#93c5fd'
  secondary: '#0284c7'
  on-secondary: '#ffffff'
  secondary-container: '#0369a1'
  on-secondary-container: '#e0f2fe'
  tertiary: '#f43f5e'
  on-tertiary: '#ffffff'
  tertiary-container: '#be123c'
  on-tertiary-container: '#ffe4e6'
  accent-cyan: '#38bdf8'
  accent-gold: '#f59e0b'
  accent-emerald: '#10b981'
  error: '#ef4444'
  on-error: '#ffffff'
  error-container: '#7f1d1d'
  on-error-container: '#fecaca'
  background: '#06070a'
  on-background: '#f8fafc'
  surface-variant: '#171c2a'
typography:
  display-2xl:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 56px
    fontWeight: '800'
    lineHeight: '1.05'
    letterSpacing: -0.03em
  display-xl:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 44px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.25'
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: '"Plus Jakarta Sans", sans-serif'
    fontSize: 10px
    fontWeight: '700'
    lineHeight: '1.4'
    letterSpacing: 0.08em
    textTransform: uppercase
  code-mono:
    fontFamily: '"JetBrains Mono", monospace'
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.4'
rounded:
  sm: 0.375rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.25rem
  2xl: 1.5rem
  3xl: 2rem
  full: 9999px
spacing:
  base: 4px
  unit: 8px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
  container-max: 1280px
---

# 🌊 Fluid Clarity — Design System (KP Bromo Web)

> **Identity:** Komisi Pemuda GKI Bromo Malang  
> **Design Frame:** *Fluid Clarity* (Stitch Canvas v2.0)  
> **Philosophy:** High-Precision Fluid Modernism, Translucent Glass Layers, and Anti-AI Slop Authenticity.

---

## 1. Brand Philosophy & Aesthetic Vision

**Fluid Clarity** is engineered to express the dynamic spiritual heartbeat of Komisi Pemuda GKI Bromo. Moving away from generic dark UI tropes, it introduces an aesthetic of **luminous clarity, fluid kinetic energy, and architectural precision**.

### 🌟 Core Visual Pillars:
1. **The Dynamic Waveform (Signature Monogram):** Represents the pulse of life, the acoustic frequency of praise, and the living Word of God flowing through the community.
2. **Fluid Glassmorphism & Specular Rims:** Translucent dark obsidian glass (`backdrop-blur-xl`, `border-white/[0.08]`) that reflects ambient light without muddy opacity.
3. **High-Contrast Editorial Typography:** Sharp geometric sans paired with structured monospace metadata for zero-bullshit readability.
4. **Anti-AI Slop Standard:** Crisp stroke-aligned SVG icons only (zero emojis in navigation/buttons), intentional high WCAG AA/AAA contrast ratios, and tactile micro-interactions.

---

## 2. Color Palette & Hierarchy

```
[ Canvas: Obsidian #06070A ] ─── [ Surface: Glass #0B0D13 ] ─── [ Border: White/8% ]
              │                                      │
              ▼                                      ▼
[ Primary: Azure #2563EB ] ────────────── [ Luminous Cyan: #38BDF8 ]
              │                                      │
              ▼                                      ▼
[ Accent Rose: #F43F5E ] ───────────────── [ Success Emerald: #10B981 ]
```

### Color Token Reference:
* **Background & Canvas:**
  * Base Obsidian Canvas: `#06070A` (`bg-obsidian-950`)
  * Elevated Glass Surface: `#0B0D13` (`bg-obsidian-900/90`)
  * Deep Island Surface: `#11141E` (`bg-obsidian-850`)
* **Primary Brand Tones:**
  * **Electric Azure (Primary):** `#2563EB` (Tailwind `blue-600`)
  * **Deep Cobalt (Container):** `#1D4ED8` (Tailwind `blue-700`)
  * **Luminous Cyan (Glow Accent):** `#38BDF8` (Tailwind `sky-400`)
* **Functional & State Accents:**
  * **Vivid Rose (Event / Photobooth / Action):** `#F43F5E` / `#E11D48`
  * **Vibrant Emerald (Success / Check-in Green):** `#10B981` / `#059669`
  * **Warm Amber (Warning / Geofence alert):** `#F59E0B`
  * **Crimson Error:** `#EF4444`

---

## 3. Typography Rules

| Style Name | Font Family | Size | Weight | Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display 2XL** | *Plus Jakarta Sans* | 56px | 800 (ExtraBold) | `-0.03em` | Hero Headlines & Banners |
| **Headline LG** | *Plus Jakarta Sans* | 32px | 700 (Bold) | `-0.02em` | Section Titles & Modal Names |
| **Headline MD** | *Plus Jakarta Sans* | 24px | 700 (Bold) | `-0.015em` | Card Headers & Major Prompts |
| **Body LG** | *Plus Jakarta Sans* | 16px | 400 (Regular) | `normal` | Primary Narrative & Guides |
| **Body MD** | *Plus Jakarta Sans* | 14px | 400 / 500 | `normal` | Subtitles, Descriptions, Forms |
| **Label Caps** | *Plus Jakarta Sans* | 10px / 11px | 700 / 800 | `0.08em` | Category Pills, Status Badges |
| **Code Mono** | *JetBrains Mono* | 12px / 13px | 500 / 700 | `tight` | Attendance Streak, Timestamps, IDs |

---

## 4. Elevation, Depth & Light

Fluid Clarity avoids heavy flat shadows. Instead, it utilizes **tonal elevation, specular hairline borders, and refractive glass**:

1. **Layer 0 (Base Canvas):** `#06070A` solid background.
2. **Layer 1 (Glass Container):** `bg-obsidian-900/90 backdrop-blur-xl border border-white/[0.08] shadow-2xl`
3. **Layer 2 (Interactive Floating Card):** `bg-obsidian-850 hover:bg-obsidian-800 border border-white/[0.06] transition-all`
4. **Specular Rim Highlight:** A 1px top border or outline with subtle white alpha to simulate light refraction on beveled glass.

---

## 5. Shape Language & Geometry

* **Corner Radii Hierarchy:**
  * **Small Badges & Tooltips:** `rounded-lg` (8px)
  * **Standard Buttons & Inputs:** `rounded-xl` (12px)
  * **Feature Cards & Modals:** `rounded-2xl` (16px) or `rounded-3xl` (24px)
  * **Status Pills & Avatars:** `rounded-full` (9999px)
* **Hit Targets:** Minimum 44x44px for touch-friendly operation on mobile and kiosk tablets.

---

## 6. Reusable Component Variants

### A. Primary Action Button (Electric Fluid)
```html
<button class="flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-sm rounded-xl shadow-lg shadow-blue-950/60 border border-blue-400/30 transition-all active:scale-[0.98]">
  <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">...</svg>
  <span>Simpan Data</span>
</button>
```

### B. Secondary Action / Glass Button
```html
<button class="flex items-center gap-2 px-4 py-2.5 bg-obsidian-800/80 hover:bg-obsidian-700/80 backdrop-blur rounded-xl text-xs font-semibold text-slate-200 border border-white/[0.08] transition-all active:scale-[0.98]">
  <span>Filter Waktu</span>
</button>
```

### C. Glassmorphism Card Container
```html
<div class="bg-obsidian-900/90 backdrop-blur-xl rounded-3xl p-6 border border-white/[0.08] shadow-2xl">
  <!-- Content -->
</div>
```

### D. Status / Method Tag (Mono Badge)
```html
<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-sky-500/10 text-sky-400 border border-sky-500/20">
  <span class="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
  Face Scan
</span>
```

---

## 7. Implementation Checklist & Anti-Slop Safeguards

- [x] **Zero Emoji in UI Controls:** Replace all emoji with stroke-aligned SVG icons.
- [x] **No Uncontrolled Glow Blobs:** Glows must be tightly bound to focus rings or laser scanlines (`stroke-dasharray`, `#38BDF8`).
- [x] **WCAG Contrast Compliant:** Text must contrast with at least 4.5:1 ratio against dark glass surfaces.
- [x] **Clean Threading & Concurrency:** Async views and canvas rendering must not freeze UI interaction.
