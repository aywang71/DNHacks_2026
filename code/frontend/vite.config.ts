import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:3001' } },
  preview: { proxy: { '/api': 'http://127.0.0.1:3001' } },
  build: {
    // The lazily requested MapLibre renderer itself is a single minified module
    // (~1 MB), so it cannot be subdivided further by the bundler. The initial
    // application chunk remains below 500 kB; use a budget that reflects the
    // intentionally deferred map-engine response.
    chunkSizeWarningLimit: 1100,
    rolldownOptions: {
      output: {
        // MapLibre is loaded lazily by MapPanel. Split its large renderer into
        // cacheable sub-chunks so no single response exceeds our 500 kB budget.
        codeSplitting: {
          groups: [{
            name: 'maplibre',
            test: /node_modules[\\/]maplibre-gl[\\/]/,
            maxSize: 450 * 1024,
          }],
        },
      },
    },
  },
})
