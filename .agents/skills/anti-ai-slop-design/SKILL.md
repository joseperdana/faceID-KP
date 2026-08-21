---
name: anti-ai-slop-design
description: Design principles and execution standards to eliminate generic AI design tropes (AI slop) and craft high-end, tactile, and culturally authentic web interfaces.
---

# 🎨 Anti-AI Slop Design Principles & Aesthetics

## ❌ What is "AI Slop" in UI/UX Design?
AI Slop refers to generic, uninspired UI artifacts that LLMs generate by default when instructed to "make it modern and pretty":
1. **Generic Neon Blobs & Glows:** Purple/cyan radial gradient blobs slapped over dark slate with no light-source logic.
2. **Emoji Abuse:** Using emojis (`🏛️`, `🎉`, `📊`, `📝`) as UI icons instead of precise, stroke-aligned SVGs.
3. **Card-in-Card Nesting Hell:** Endless rounded rectangular cards inside other rounded cards without visual hierarchy.
4. **Muted Unreadable Contrast:** Low-contrast gray-on-dark-gray text (`text-slate-500` on `bg-slate-900`) that fails WCAG accessibility in daylight.
5. **Generic SaaS Homogeneity:** Everything looking like an unfinished crypto dashboard or generic template.

---

## ✨ The Premium Design Standard for FaceID-KP

### 1. Typography Hierarchy (Editorial & High-Contrast)
- **Primary Interface Font:** *Plus Jakarta Sans* / *Inter* (500, 600, 800 weights).
- **Display & Heritage Accents (KP45 & Titles):** Editorial high-contrast serif (*Cinzel* or *Playfair Display*) for Indonesian celebration banners.
- **Monospace Metadata:** *JetBrains Mono* / *Fira Code* for timestamps, confidence scores, and streak numbers.

### 2. Palette: Deep Obsidian & Warm Nusantara Tones
- **Backgrounds:** Obsidian Canvas (`#090A0F`), Surface Elevated (`#12151E`), Card Hover (`#181D2A`).
- **Borders:** Ultra-crisp 1px semi-transparent borders (`border-white/[0.08]`, `border-white/[0.12]`).
- **Brand Accents (Merah Putih & Heritage):**
  - Crimson / Vermilion: `#E11D48` & `#BE123C` (vibrant Indonesian red).
  - Antique Gold / Brass: `#D97706` & `#B45309` (refined batik warmth).
  - High-Contrast Text: `#F8FAFC` (pure readability), `#94A3B8` (secondary metadata).

### 3. Crisp SVG Iconography (Zero Emojis in Core Navigation)
- All navigation buttons and status indicators must use sharp, scalable SVG line icons with consistent 2px stroke weight.

### 4. Tactile Polish & Micro-interactions
- Active press states: `active:scale-[0.98] transition-transform duration-100`.
- Smooth focus states with high accessibility outline.
