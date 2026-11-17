/// <reference types="vitest/config" />
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

// Served from https://robertgeraldsenasin.github.io/whyfinder/ on GitHub Pages.
export default defineConfig({
  base: process.env.WHYFINDER_BASE ?? '/whyfinder/',
  plugins: [svelte()],
  // tokens.css and stats.json live outside web/ (docs/design, data/): one source of truth.
  server: { fs: { allow: ['..'] } },
  worker: { format: 'es' },
  build: { target: 'es2022', sourcemap: true },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'node',
    testTimeout: 60_000,
  },
});
