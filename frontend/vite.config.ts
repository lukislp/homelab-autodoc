/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/admin/',
  server: {
    // dev-server proxy so `npm run dev` can talk to a locally running
    // autodoc-server (see ../server) without a CORS dance.
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/device': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      // App.tsx/main.tsx are thin composition roots (routing between views,
      // bootstrapping) - the same rationale other packages use for excluding
      // generated/UI-only code from the coverage number.
      include: ['src/api/**', 'src/hooks/**', 'src/components/**'],
    },
  },
})
