/**
 * Shared Tailwind theme for every page in the app.
 *
 * This configuration used to be copy-pasted into five HTML files, and they had
 * drifted: obsidian-800 was #171c2a on the kiosk and #151926 everywhere else,
 * and the kiosk was missing the `azure` palette entirely. Because index.js
 * injects markup using bg-azure-600, the kiosk's "Cari Nama Manual" and
 * "Check-in" buttons rendered with no background at all — plain white text on a
 * dark panel, in the one screen where somebody needs to find the fallback.
 *
 * Tailwind generates nothing for a colour that is not in the config, and there
 * is no build step to catch it, so a single shared file is the fix.
 *
 * Load before the Tailwind CDN script on every page.
 */
window.tailwind = window.tailwind || {};
window.tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        obsidian: {
          950: '#0b0d13',
          900: '#0f131c',
          850: '#131822',
          800: '#151926',
          750: '#1b2130',
          700: '#222839',
        },
        azure: {
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in .18s ease-out',
      },
    },
  },
};
