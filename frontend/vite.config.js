import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
export default defineConfig({
    plugins: [react()],
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
});
