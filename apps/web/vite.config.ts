import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import type { IncomingMessage } from 'http'

// SPA routes (/market, /schemes, /data-sources) share their path prefix with
// backend API routes, so browser navigations to them must be served index.html
// instead of being proxied to the API (rewrite += next() -> Vite SPA fallback).
const spaBypass = (req: IncomingMessage) =>
  req.headers.accept?.includes('text/html') ? '/index.html' : undefined

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/analysis': { target: 'http://localhost:8000', changeOrigin: true },
      '/geojson': { target: 'http://localhost:8000', changeOrigin: true },
      '/schemes': { target: 'http://localhost:8000', changeOrigin: true, bypass: spaBypass },
      '/locations': { target: 'http://localhost:8000', changeOrigin: true },
      '/businesses': { target: 'http://localhost:8000', changeOrigin: true },
      '/market': { target: 'http://localhost:8000', changeOrigin: true, bypass: spaBypass },
      '/financial': { target: 'http://localhost:8000', changeOrigin: true },
      '/data-sources': { target: 'http://localhost:8000', changeOrigin: true, bypass: spaBypass },
      '/ai': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          leaflet: ['leaflet', 'react-leaflet', 'react-leaflet-cluster', 'leaflet.markercluster'],
          charts: ['recharts'],
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
})
