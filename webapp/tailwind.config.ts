import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Cinematic charcoal surfaces (near-black, not pure black)
        ink: "#070709",       // app background
        panel: "#0d0d12",     // base panel
        surface: "#121218",   // raised panel
        surface2: "#17171f",  // input / hover
        edge: "#23232e",      // subtle border
        edge2: "#2e2e3b",     // stronger border
        primary: "#7c6aff",   // accent (used sparingly)
        primary2: "#9d92ff",
        success: "#46d39a",
        warn: "#e8a33d",
        danger: "#ff5d76",
        muted: "#7e7e92",     // secondary text
        faint: "#54545f",     // tertiary text
        text: "#ecedf2",      // primary text
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(124,106,255,0.35), 0 6px 30px -10px rgba(124,106,255,0.45)",
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 12px 40px -20px rgba(0,0,0,0.8)",
        pop: "0 18px 60px -18px rgba(0,0,0,0.75)",
      },
      borderRadius: {
        lg: "8px",
        xl: "10px",
        "2xl": "14px",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s linear infinite",
        "fade-in": "fade-in 0.18s ease-out",
        "scale-in": "scale-in 0.14s ease-out",
        "slide-up": "slide-up 0.22s ease-out",
        "pulse-soft": "pulse-soft 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
