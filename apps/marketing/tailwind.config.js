/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#f4faf7",
        "ink-soft": "#c9ddd4",
        steel: "#8eaaa0",
        mist: "#2c433b",
        paper: "#0b1411",
        surface: "#142820",
        accent: "#3ee9c9",
        "accent-deep": "#1bc4a8",
        "accent-soft": "#134038",
        "accent-glow": "#5ff0d4",
        warm: "#d4b483",
      },
      fontFamily: {
        display: ["Syne", "system-ui", "sans-serif"],
        body: ["IBM Plex Sans", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
