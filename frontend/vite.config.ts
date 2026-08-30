import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // Function form: object form matches exact module ids only, so
        // 'react-dom/client' (a different id than 'react-dom') stayed in the
        // entry chunk and dragged react-dom internals with it. Route every
        // dependency into the stable vendor chunk (better long-term caching);
        // the Supabase SDK stays separate so it is only fetched when a
        // dynamic import needs it.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('@supabase')) return 'supabase'
          return 'vendor'
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // vitest owns src/ unit tests; e2e/*.spec.ts belongs to Playwright (npm run e2e).
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
