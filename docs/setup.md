# Local Development

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- Docker Compose
- Ollama
- Tavily API key

## Start local dependencies

From the repository root, start Qdrant:

```sh
docker compose up -d
```

Pull the default local models:

```sh
ollama pull qwen3:4b-instruct
ollama pull embeddinggemma
```

## Configure and run the backend

`uv sync` creates and manages the project environment:

```sh
cd backend
uv sync
cp .env.example .env
```

Set `TAVILY_API_KEY=your_tavily_api_key` in `backend/.env`. The committed `.env.example` is the authoritative list of settings; it includes provider selection, Ollama endpoints/models, Qdrant settings, Cloud Inference, CORS, retrieval settings, and document limits. Do not commit populated `.env` files or real credentials.

Start FastAPI:

```sh
uv run uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; `GET /health` is its health check.

## Configure and run the frontend

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. `frontend/.env.example` contains the only public frontend setting, `VITE_API_BASE_URL`, for a separately deployed API. It must never contain backend/provider secrets.

## Local defaults

The local defaults use Ollama `qwen3:4b-instruct` for generation and `embeddinggemma` for 768-dimensional embeddings, with Qdrant at `http://localhost:6333`. Production uses a separate 384-dimensional Qdrant Cloud collection; do not mix their collection settings.

## Validate

Backend:

```sh
cd backend
uv run pytest
uv run ruff check .
uv run python scripts/run_offline_evaluation.py
```

Frontend:

```sh
cd frontend
npm run lint
npm run test:run
npm run build
```

The offline evaluator is deterministic and does not call providers or the network. It writes `backend/offline-evaluation.json`, a local generated artifact that should not be committed.
