import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Saída compilada vai direto para app/web (servida pelo FastAPI). Em desenvolvimento, /api é redirecionado.
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: { outDir: '../app/web', emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8765' } },
})
