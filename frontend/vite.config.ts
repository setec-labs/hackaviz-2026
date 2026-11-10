import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
  },
  build: {
    // MapLibre + deck.gl forment un socle volumineux mais indivisible pour ce prototype.
    chunkSizeWarningLimit: 2500,
  },
});
