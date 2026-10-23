import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The backend (FastAPI) listens on 8000. The browser talks to /api on the same origin and Vite
// forwards it, so there are no CORS problems in development or in the production preview.
const backend = { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: backend },
  preview: { proxy: backend },
})
