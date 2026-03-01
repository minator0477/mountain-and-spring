import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/meizan.geojson': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
