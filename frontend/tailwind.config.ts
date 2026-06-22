import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Couleur primaire pilotée par la config tenant (variable CSS).
        primary: "rgb(var(--zo-primary) / <alpha-value>)",
        surface: "rgb(var(--zo-surface) / <alpha-value>)",
        ink: "rgb(var(--zo-ink) / <alpha-value>)",
        muted: "rgb(var(--zo-muted) / <alpha-value>)",
      },
      borderRadius: { xl: "0.875rem", "2xl": "1.25rem" },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { "fade-in": "fade-in 0.2s ease-out" },
    },
  },
  plugins: [],
};

export default config;
