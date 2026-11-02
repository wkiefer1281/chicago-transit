import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


// In dev the API runs separately: `uvicorn server.app:app --reload` (port 8000).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: {
    chunkSizeWarningLimit: 1500, // vega is large; it is the point of the app
  },
  test: { include: ["src/**/*.test.ts"] },
});
