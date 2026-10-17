import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API and media are served by the FastAPI process on 8787; the dev server proxies them.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/media': 'http://127.0.0.1:8787',
    },
  },
})
