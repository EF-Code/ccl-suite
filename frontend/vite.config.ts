import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    // Keep the initial dashboard small and serve lazy workspace chunks via the
    // API's explicit /assets mount. Small fonts and other assets may be inlined.
    assetsInlineLimit: 100_000,
    // Keep 550 kB as a visible review threshold; do not raise it just to hide
    // growth.
    chunkSizeWarningLimit: 550,
  },
  server: {
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/permissions": "http://127.0.0.1:8000",
      "/upload-policy": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/research": "http://127.0.0.1:8000",
      "/project-folders": "http://127.0.0.1:8000",
      "/users": "http://127.0.0.1:8000",
      "/security-events": "http://127.0.0.1:8000",
      "/security-dashboard": "http://127.0.0.1:8000",
      "/operations": "http://127.0.0.1:8000",
      "/workflows": "http://127.0.0.1:8000",
      "/approvals": "http://127.0.0.1:8000",
    },
  },
  preview: {
    port: 4173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/permissions": "http://127.0.0.1:8000",
      "/upload-policy": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/research": "http://127.0.0.1:8000",
      "/project-folders": "http://127.0.0.1:8000",
      "/users": "http://127.0.0.1:8000",
      "/security-events": "http://127.0.0.1:8000",
      "/security-dashboard": "http://127.0.0.1:8000",
      "/operations": "http://127.0.0.1:8000",
      "/workflows": "http://127.0.0.1:8000",
      "/approvals": "http://127.0.0.1:8000",
    },
  },
});
