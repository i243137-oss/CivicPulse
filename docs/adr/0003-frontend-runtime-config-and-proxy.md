# ADR-0003: Frontend Runtime Configuration and API Reverse Proxying

## Status

Accepted

## Date

2026-09-27

## Context

In modern single-page applications built with Vite, TypeScript, and React, frontend assets are compiled and bundled into static HTML, CSS, and JavaScript files during the `npm run build` step.

A common anti-pattern is baking backend API target URLs (such as `http://localhost:8000` or environment-specific hostnames like `https://api.dev.civicpulse.org`) into the client JavaScript bundle via `import.meta.env.VITE_API_BASE_URL` at build time. Doing so violates the fundamental Twelve-Factor App principle of **Build, Release, Run** (and build-once-deploy-many):

1. **Environment-Specific Images**: An image built for local development or staging cannot run in production or a Kubernetes cluster without rebuilding the entire JavaScript artifact from source.
2. **CORS and Origin Friction**: Communicating from browser origins (e.g., `http://localhost:5173` or `http://civicpulse.local`) directly to distinct backend origins (e.g., `http://backend:8000`) requires CORS headers, preflight requests (`OPTIONS`), and complex origin coordination.
3. **Container Network Isolation**: In containerized and Kubernetes environments, the backend and database reside on private networks inaccessible directly by public browser clients.

## Considered Options

### Option 1: Runtime Window Configuration (`/config.js`)

- **Mechanism**: Nginx or an entrypoint shell script dynamically generates a `/config.js` file at container startup from container environment variables (e.g. `window.__ENV__ = { API_URL: process.env.BACKEND_URL }`).
- **Pros**: Dynamic environment variable injection at container startup.
- **Cons**: Requires additional entrypoint templating scripts in container startup, adds an extra network request to fetch `/config.js` before application mount, and does not eliminate CORS concerns between frontend and backend hosts.

### Option 2: Reverse Proxying via Relative `/api` Paths (Selected)

- **Mechanism**: The frontend API client issues requests exclusively to relative paths (`/api/complaints`, `/api/stats`, etc.).
  - **Local Development**: Vite dev server proxies `/api` to `http://localhost:8000` using the Vite development server proxy (`vite.config.ts`).
  - **Docker Compose & Production Nginx**: The production Nginx container (`nginx:alpine`) serves static bundles and reverse-proxies `/api/` directly to `http://backend:8000/api/` through an upstream block (`nginx.conf`).
  - **Kubernetes**: The Ingress controller routes `/` to `civicpulse-frontend` Service and `/api` to `civicpulse-backend` Service under a single unified host.
- **Pros**:
  - **Zero Baked-In URLs**: The client bundle contains 0 references to hostnames or ports. The exact same container image (`civicpulse-frontend:<sha>`) runs identically in local dev, staging, Docker Compose, and Kubernetes.
  - **Zero CORS Overhead**: The browser interacts with a single origin. No CORS headers or preflight `OPTIONS` requests are needed.
  - **Enhanced Security**: Backends remain unexposed on public container ports; ingress and edge proxies handle routing.
- **Cons**: Requires reverse proxy configuration (Vite proxy for local dev, Nginx config for Docker, Ingress for Kubernetes).

## Decision

We adopt **Option 2: Reverse Proxying via Relative `/api` Paths**.

1. **Typed Client Architecture**:
   The centralized API client in `frontend/src/api/client.ts` uses relative URLs (`/api/...`). No backend origin, hostname, or API keys are ever stored in the browser bundle or environment files.

2. **Vite Development Server Proxy**:
   In `frontend/vite.config.ts`, Vite dev server proxies `/api` to `http://localhost:8000`:

   ```typescript
   server: {
     host: "0.0.0.0",
     port: 5173,
     proxy: {
       "/api": {
         target: "http://localhost:8000",
         changeOrigin: true,
       },
     },
   }
   ```

3. **Production Nginx Gateway**:
   The production multi-stage Dockerfile (`node:22-alpine` builder, `nginx:1.27-alpine` runner) installs `frontend/nginx.conf`, which:
   - Serves the Single Page Application bundle with `try_files $uri $uri/ /index.html`
   - Reverse proxies `/api/` to `http://backend:8000/api/`
   - Reverse proxies `/health` to `http://backend:8000/health`
     This satisfies the assignment's build-once-deploy-many requirement and ensures identical client behavior in standalone containers and behind Kubernetes ingress.

## Consequences

- **Positive**:
  - Complete compliance with build-once-deploy-many: the frontend container image built in CI is promoted across staging and production without rebuilding.
  - Complete elimination of CORS configuration and preflight latency.
  - No secrets or backend infrastructure endpoints leaked to client browser bundles.
  - Consistent behavior across local development (Vite), Compose (Nginx), and Kubernetes (Ingress).
- **Negative**:
  - Local developers running the frontend without Vite's dev proxy must ensure an HTTP proxy or backend is listening on `/api`.
