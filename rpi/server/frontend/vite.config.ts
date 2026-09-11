import preact from '@preact/preset-vite';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [preact()],
  root: '.',
  base: '/',
  build: {
    outDir: '../static/dist',
    emptyDirBeforeWrite: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    // API_TARGET=https://gardener.example npx vite, to develop against a live Pi
    proxy: Object.fromEntries(
      ['/api', '/health', '/sse'].map((path) => [
        path,
        {
          target: process.env.API_TARGET ?? 'http://localhost:5000',
          changeOrigin: true,
          secure: false,
        },
      ]),
    ),
  },
  resolve: {
    alias: {
      '@': resolve(import.meta.dirname, 'src'),
    },
  },
});
