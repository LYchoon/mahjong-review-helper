/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // chess.com-style review label colors
        best: "#81b64c",
        good: "#95c75a",
        inaccuracy: "#f7c948",
        mistake: "#ffa459",
        blunder: "#fa412d",
      },
    },
  },
  plugins: [],
};
