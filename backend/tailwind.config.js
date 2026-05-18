/** Tailwind config для Wagtail-шаблонов.
 *
 * Сборка:
 *   cd backend/
 *   npx tailwindcss -i ./static/css/main.input.css -o ./static/css/main.css --minify
 *
 * Или в watch-режиме при разработке:
 *   npx tailwindcss -i ./static/css/main.input.css -o ./static/css/main.css --watch
 *
 * Зависимости устанавливаются автоматически через npx; либо явно:
 *   npm install -D tailwindcss @tailwindcss/typography
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./apps/**/templatetags/*.py",  // если в тегах будут классы — захватит
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        linguistic: ["Charis SIL", "Gentium Plus", "Noto Sans", "serif"],
      },
      typography: ({ theme }) => ({
        DEFAULT: {
          css: {
            color: theme("colors.stone.800"),
            maxWidth: "none",
            lineHeight: "1.7",
            a: {
              color: theme("colors.stone.900"),
              textDecoration: "underline",
              textDecorationColor: theme("colors.stone.400"),
              "&:hover": { textDecorationColor: theme("colors.stone.900") },
            },
            "h2, h3, h4": { color: theme("colors.stone.900") },
            blockquote: {
              borderLeftColor: theme("colors.stone.300"),
              color: theme("colors.stone.700"),
            },
          },
        },
      }),
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
};
