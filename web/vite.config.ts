import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // The deploy number shown in the header. deploy.sh sets APP_VERSION when it
  // builds the image; a local dev build says "dev".
  define: { __APP_VERSION__: JSON.stringify(process.env.APP_VERSION ?? 'dev') },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    // The dev server proxies to a local uvicorn; in production nginx proxies /api
    // itself, so the app always calls the same relative paths.
    proxy: { '/api': { target: process.env.QS_API_URL ?? 'http://localhost:8000', changeOrigin: true } },
  },
})
