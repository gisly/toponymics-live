/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        // Для эвенкийских форм и IPA — Charis SIL
        linguistic: ["Charis SIL", "Gentium Plus", "Noto Sans", "serif"],
      },
    },
  },
  plugins: [],
};
