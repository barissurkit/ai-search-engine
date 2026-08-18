# AI Search frontend

React, TypeScript, and Vite foundation for the AI Search interface.

## Local development

```sh
npm install
npm run dev
```

Requests to `/api` proxy to `http://localhost:8000` while using the Vite dev server. Set `VITE_API_BASE_URL` to a backend origin when the frontend is deployed separately. No API keys belong in this application.

## Validation

```sh
npm run lint
npm run test:run
npm run build
```
