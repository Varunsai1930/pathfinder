import { defineConfig } from '@playwright/test'

/**
 * E2E smoke: runs the real Vite dev server with a fake Supabase project and a
 * mocked backend API (see e2e/app.spec.ts). Supabase auth is stubbed at the
 * localStorage/session layer — the OTP flow itself is Supabase's, not ours.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5177',
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: 'npm run dev -- --port 5177 --strictPort',
    url: 'http://localhost:5177',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      VITE_SUPABASE_URL: 'http://localhost:54321',
      VITE_SUPABASE_ANON_KEY: 'test-anon-key',
      VITE_API_URL: 'http://127.0.0.1:9999',
    },
  },
})
