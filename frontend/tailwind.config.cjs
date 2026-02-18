/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "app-bg-primary": "var(--bg-primary)",
        "app-bg-secondary": "var(--bg-secondary)",
        "app-bg-tertiary": "var(--bg-tertiary)",
        "app-bg-hover": "var(--bg-hover)",
        "app-card": "var(--bg-card)",
        "app-text-primary": "var(--text-primary)",
        "app-text-secondary": "var(--text-secondary)",
        "app-text-muted": "var(--text-muted)",
        "app-border": "var(--border-color)",
        "app-accent-blue": "var(--accent-blue)",
        "app-accent-green": "var(--accent-green)",
        "app-accent-red": "var(--accent-red)",
      },
      fontFamily: {
        sans: ["Space Grotesk", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        app: "var(--border-radius)",
        "app-sm": "var(--border-radius-sm)",
      },
      boxShadow: {
        "app-sm": "var(--shadow-sm)",
        "app-md": "var(--shadow-md)",
        "app-lg": "var(--shadow-lg)",
      },
      gridTemplateColumns: {
        "fit-220": "repeat(auto-fit, minmax(220px, 1fr))",
        "fit-200": "repeat(auto-fit, minmax(200px, 1fr))",
        "fit-190": "repeat(auto-fit, minmax(190px, 1fr))",
        "fit-185": "repeat(auto-fit, minmax(185px, 1fr))",
      },
    },
  },
  plugins: [],
};
