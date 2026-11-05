/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#102421",
        tide: "#0f6e68",
        deep: "#072e2c",
        foam: "#f4f7f5",
        gold: "#9a7040",
        line: "#d5e2de",
      },
      fontFamily: {
        display: ["var(--font-display)", "Palatino Linotype", "Georgia", "serif"],
        sans: ["var(--font-sans)", "Nirmala UI", "Segoe UI", "sans-serif"],
        bn: ["var(--font-bn)", "Nirmala UI", "Noto Sans Bengali", "sans-serif"],
      },
      boxShadow: {
        card: "0 18px 50px rgba(7, 46, 44, 0.08)",
      },
    },
  },
  plugins: [],
};
