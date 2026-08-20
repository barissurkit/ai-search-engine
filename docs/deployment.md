# Deployment

| Service | Production role |
| --- | --- |
| [Vercel](https://ai-search-engine-wine-three.vercel.app) | React/Vite frontend |
| [Render](https://ai-search-engine-api.onrender.com/health) | FastAPI backend |
| Qdrant Cloud | Vector database and Cloud Inference embeddings |
| Ollama Cloud | `gpt-oss:20b` generation |
| Tavily | Live Web search |

## Frontend

[`frontend/vercel.json`](../frontend/vercel.json) rewrites all paths to `index.html`, so direct navigation and refresh of `/c/:id` resolve through the SPA. The public frontend API origin is configured with `VITE_API_BASE_URL`; it must not contain provider credentials.

## Backend

[`render.yaml`](../render.yaml) defines the Render Python web service with `backend/` as its root, a frozen production dependency install, Uvicorn startup, and `/health` as the health-check path. Production CORS allows the exact Vercel frontend origin.

The API supports the `GET` health lifecycle plus `POST` search/answer/upload work and `DELETE` document cleanup. Production environment variables are configured in the hosting platforms; secrets such as Tavily, Qdrant, and Ollama credentials must never be committed.

## Production retrieval configuration

Production uses Qdrant Cloud Inference model `intfloat/multilingual-e5-small` at 384 dimensions with collection `ai_search_engine_cloud_384`. Ollama Cloud provides `gpt-oss:20b` generation. Web vectors are temporary per request; selected file vectors persist until document or conversation cleanup.

## Operational limits

Render's free tier can cold-start after inactivity. Conversation history remains in browser IndexedDB rather than a backend account or synchronization service.
