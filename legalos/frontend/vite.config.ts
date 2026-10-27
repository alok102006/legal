import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Docker on Windows/macOS does not forward file-change events from the host into the container,
    // so poll for changes (otherwise the dev server keeps serving stale code).
    watch: { usePolling: true, interval: 300 },
  }
})
