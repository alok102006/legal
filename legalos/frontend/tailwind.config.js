/** CSS-variable colours that still support opacity modifiers such as bg-critical/40 (via color-mix). */
const v = (name) => ({ opacityValue }) =>
  opacityValue === undefined || opacityValue === '1'
    ? `var(${name})`
    : `color-mix(in srgb, var(${name}) calc(${opacityValue} * 100%), transparent)`;

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ---- new design system (CSS-variable driven; light/dark handled in index.css)
        app: v('--bg'),
        surface: { DEFAULT: v('--surface'), 2: v('--surface-2') },
        line: { DEFAULT: v('--border'), strong: v('--border-strong') },
        ink: { DEFAULT: v('--text'), 2: v('--text-2'), 3: v('--text-3') },
        primary: {
          DEFAULT: v('--primary'),
          hover: v('--primary-hover'),
          soft: v('--primary-soft'),
          ink: v('--primary-ink'),
          on: v('--on-primary'),
        },
        good: { DEFAULT: v('--good'), ink: v('--good-ink'), soft: v('--good-soft') },
        warn: { DEFAULT: v('--warn'), ink: v('--warn-ink'), soft: v('--warn-soft') },
        serious: { DEFAULT: v('--serious'), ink: v('--serious-ink'), soft: v('--serious-soft') },
        critical: { DEFAULT: v('--critical'), ink: v('--critical-ink'), soft: v('--critical-soft') },
        peach: { DEFAULT: v('--peach'), ink: v('--peach-ink'), line: v('--peach-line') },
        lavender: { DEFAULT: v('--lavender'), ink: v('--lavender-ink') },
        teal: { DEFAULT: v('--teal'), soft: v('--teal-soft') },

      },
      fontFamily: {
        sans: ['Figtree', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        serif: ['Newsreader', 'Georgia', 'Cambria', 'serif'],          // readable body serif for contract and notice text
        display: ['Instrument Serif', 'Newsreader', 'Georgia', 'serif'], // hero lines and section titles
        mono: ['Geist Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: { xl: '14px', '2xl': '18px', '3xl': '24px' },
      boxShadow: {
        card: 'var(--shadow)',
        raised: 'var(--shadow-raised)',
        float: 'var(--shadow-float)',
        inset: 'var(--shadow-inset)',
      },
    },
  },
  plugins: [],
}
