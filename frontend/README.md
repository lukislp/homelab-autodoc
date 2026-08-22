# autodoc-admin-ui

The admin app for [homelab-autodoc](../README.md): the setup wizard and the pending-cluster-registration approval screen for the [server](../server). React + TypeScript + Vite, served by the server itself at `/admin`.

The MkDocs Material documentation site (the public part of homelab-autodoc) is generated separately by the [generator](../generator) - this app is only the small admin surface behind login.

## Layers

Mirrors the backend's `logic`/`web` split:

- [`api/`](src/api) - the only place that calls `fetch()`. `client.ts` is the raw HTTP layer (credentials, JSON, error handling → `ApiError`); `auth.ts`/`devices.ts` are typed functions on top of it.
- [`hooks/`](src/hooks) - data-fetching state (`useAuthStatus`, `usePendingDevices`), built on `api/`. No JSX.
- [`components/`](src/components) - presentational only (`SetupForm`, `DeviceList`). They receive data and callbacks as props and never call `fetch` themselves.
- [`App.tsx`](src/App.tsx) - the only place that decides which view to show, based on `useAuthStatus()`.

## Usage

```bash
npm install

# Dev server (proxies /api, /auth, /device to a locally running autodoc-server on :8000)
npm run dev

# Production build - the server serves this directory at /admin by default
# (override with AUTODOC_ADMIN_UI_DIR)
npm run build
```

## Development

```bash
npm install
npm run lint    # oxlint
npm run build   # tsc -b && vite build - the type-check IS the build
npm run test    # vitest
```
