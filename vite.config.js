import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/meizan.geojson': 'http://localhost:8000',
      '/springs.geojson': 'http://localhost:8000',
      '/meizan': 'http://localhost:8000',
      '/spring': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
