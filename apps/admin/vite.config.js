import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteApiProxy } from "../../server/vite-api-proxy.mjs";

export default defineConfig(({ mode }) => ({
  base: process.env.ADMIN_BASE_PATH || "/",
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": viteApiProxy(mode, process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"),
      "/ws": {
        target: process.env.WS_PROXY_TARGET || "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
}));
