import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { viteApiProxy } from '../../server/vite-api-proxy.mjs';

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': viteApiProxy(mode, process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000'),
    },
  },
}));
