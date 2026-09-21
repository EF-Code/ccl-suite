import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    // The API serves one self-contained static HTML artifact; inline the
    // bundled Geist fonts so it does not depend on an unserved /assets path.
    assetsInlineLimit: 100_000,
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
      "/workflows": "http://127.0.0.1:8000",
      "/approvals": "http://127.0.0.1:8000",
    },
  },
});
