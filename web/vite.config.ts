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
    //
    // changeOrigin must stay false. With it on, the proxy rewrites Host to the
    // target ("localhost"), so opening the dev server at http://127.0.0.1:5173
    // sends Origin: 127.0.0.1 against Host: localhost and the same-origin guard
    // (api/app/csrf.py) 403s every save. Off, Host is forwarded unchanged and the
    // hostnames match however the dev server was opened.
    proxy: { '/api': { target: process.env.QS_API_URL ?? 'http://localhost:8000', changeOrigin: false } },
  },
})
