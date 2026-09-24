import { defineConfig } from 'vite';

export default defineConfig({
  // Caminhos relativos: o build funciona aberto de qualquer subpasta.
  base: './',
  server: {
    port: 5173,
    host: 'localhost',
  },
  preview: {
    port: 4173,
  },
  build: {
    target: 'es2022',
    sourcemap: true,
    // three.js sozinho ocupa ~700 KB minificado.
    chunkSizeWarningLimit: 1200,
  },
});
