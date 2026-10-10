/** @type {import('tailwindcss').Config} */
// Tokens mirror frontend/DESIGN.md. Components must read these — no ad-hoc hex.
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}", "./apps/hire/index.html", "./apps/hire/src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Neutral + surface tokens are CSS-variable driven so a `.dark` class can
        // remap them platform-wide. Light values equal the previous hex exactly,
        // so light mode renders identically. See index.css :root / .dark.
        ink: {
          950: "rgb(var(--c-ink-950) / <alpha-value>)",
          900: "rgb(var(--c-ink-900) / <alpha-value>)",
          800: "rgb(var(--c-ink-800) / <alpha-value>)",
          700: "rgb(var(--c-ink-700) / <alpha-value>)",
        },
        // Elevated dark surfaces (formerly bg-ink-*): buttons, sidebar, headers.
        invert: {
          950: "rgb(var(--c-invert-950) / <alpha-value>)",
          900: "rgb(var(--c-invert-900) / <alpha-value>)",
          800: "rgb(var(--c-invert-800) / <alpha-value>)",
        },
        // Card / panel surface (formerly bg-white).
        surface: {
          DEFAULT: "rgb(var(--c-surface) / <alpha-value>)",
          2: "rgb(var(--c-surface-2) / <alpha-value>)",
        },
        slate: {
          50: "rgb(var(--c-slate-50) / <alpha-value>)",
          100: "rgb(var(--c-slate-100) / <alpha-value>)",
          200: "rgb(var(--c-slate-200) / <alpha-value>)",
          300: "rgb(var(--c-slate-300) / <alpha-value>)",
          400: "rgb(var(--c-slate-400) / <alpha-value>)",
          500: "rgb(var(--c-slate-500) / <alpha-value>)",
          600: "rgb(var(--c-slate-600) / <alpha-value>)",
          700: "rgb(var(--c-slate-700) / <alpha-value>)",
          800: "rgb(var(--c-slate-800) / <alpha-value>)",
          900: "rgb(var(--c-slate-900) / <alpha-value>)",
          950: "rgb(var(--c-slate-950) / <alpha-value>)",
        },
        brand: {
          400: "#3B82F6",
          500: "#2563EB",
          600: "#1D4ED8",
        },
        amber: {
          400: "#FBBF24",
          500: "#F59E0B",
          600: "#D97706",
        },
        teal: {
          400: "#2DD4BF",
          500: "#0D9488",
          600: "#0F766E",
        },
        rose: {
          500: "#E11D48",
          600: "#BE123C",
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "24px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,27,51,0.04), 0 8px 24px rgba(11,27,51,0.08)",
        lift: "0 12px 32px rgba(11,27,51,0.14)",
      },
      keyframes: {
        "xp-fill": { from: { width: "0%" }, to: { width: "var(--xp)" } },
        "pop-in": {
          "0%": { transform: "scale(0.8)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
      animation: {
        "xp-fill": "xp-fill 700ms ease-out forwards",
        "pop-in": "pop-in 220ms ease-out both",
        float: "float 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
