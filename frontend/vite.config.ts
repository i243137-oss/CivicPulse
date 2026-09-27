// ═══════════════════════════════════════════════════════════════
//  CivicPulse Frontend — Vite Configuration
// ═══════════════════════════════════════════════════════════════
//  Responsibility:
//    Configures the Vite dev server and production build for the
//    React TypeScript frontend. Proxies API requests to the
//    FastAPI backend during local development.
// ═══════════════════════════════════════════════════════════════

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});

