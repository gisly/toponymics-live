import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

/**
 * Конфигурация Vite с двумя режимами:
 *
 * 1) DEV / SPA-режим (по умолчанию, для разработки на http://localhost:5173):
 *    `npm run dev` или `vite`
 *    Точка входа: index.html → src/main.tsx → React Router → весь App
 *
 * 2) LIBRARY-режим (для встраивания в Wagtail-страницу):
 *    `npm run build:lib` или `BUILD_LIB=1 vite build`
 *    Точка входа: src/mount.tsx → UMD-бандл с window.ToponymicsMap
 *    Выход: dist-lib/toponymics-map.umd.js + dist-lib/toponymics-map.css
 *    Эти файлы потом копируются в backend/static/map-bundle/
 */
const BUILD_LIB = process.env.BUILD_LIB === "1" || process.env.BUILD_LIB === "true";

export default defineConfig({
  plugins: [react()],
  // В library-режиме надо подставить process.env.NODE_ENV вручную,
  // потому что в браузере process не существует, а React/tanstack-query
  // делают на эту переменную проверки.
  define: BUILD_LIB
    ? {
        "process.env.NODE_ENV": JSON.stringify("production"),
        "process.env": JSON.stringify({}),
      }
    : undefined,
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      // В Docker, polling работает надёжнее, чем inotify
      usePolling: true,
      interval: 300,
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: BUILD_LIB
    ? {
        // Library-mode: собираем как переиспользуемый бандл
        lib: {
          entry: path.resolve(__dirname, "src/mount.tsx"),
          name: "ToponymicsMap",
          fileName: () => "toponymics-map.umd.js",
          formats: ["umd"],
        },
        outDir: "dist-lib",
        emptyOutDir: true,
        cssCodeSplit: false,
        sourcemap: true,
        rollupOptions: {
          output: {
            // CSS будет в одном файле toponymics-map.css
            assetFileNames: (assetInfo) => {
              if (assetInfo.name?.endsWith(".css")) return "toponymics-map.css";
              return "assets/[name]-[hash][extname]";
            },
            // Делаем чтобы window.ToponymicsMap был самим объектом, а не {default: {...}}
            exports: "default",
          },
        },
      }
    : {
        // SPA-mode: обычная сборка для standalone-разработки
        outDir: "dist",
        emptyOutDir: true,
      },
});
