import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx

from app.api.dependencies.rag import get_rag_service
from app.core.config import Settings
from app.rag.evaluation import CitationBenchmarkRunner, format_citation_benchmark_report


async def preflight(settings: Settings) -> None:
    """Verify required local services and configured models without exposing secrets."""
    if settings.tavily_api_key is None or not settings.tavily_api_key.get_secret_value().strip():
        raise RuntimeError("Tavily API key is not configured.")

    timeout = httpx.Timeout(settings.ollama_request_timeout_seconds)
    async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
        ollama_response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        ollama_response.raise_for_status()
        payload = ollama_response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise TypeError("Ollama model list was invalid.")
        names = {
            model.get("name")
            for model in models
            if isinstance(model, dict)
            if isinstance(model.get("name"), str)
        }
        installed_model_bases = {name.split(":", maxsplit=1)[0] for name in names}
        configured_models = {
            settings.ollama_generation_model,
            settings.ollama_embedding_model,
        }
        missing_models = {
            model
            for model in configured_models
            if model not in names
            and not (":" not in model and model in installed_model_bases)
        }
        if missing_models:
            raise RuntimeError("Required Ollama model is unavailable.")

        qdrant_response = await client.get(f"{settings.qdrant_url.rstrip('/')}/collections")
        qdrant_response.raise_for_status()


async def main() -> None:
    settings = Settings()
    try:
        await preflight(settings)
    except (httpx.HTTPError, TypeError, ValueError, RuntimeError) as exc:
        print(f"BLOKE: benchmark environment preflight failed: {exc}")
        return

    try:
        async for rag_service in get_rag_service(settings):
            report = await CitationBenchmarkRunner().run(rag_service)
            print(format_citation_benchmark_report(report))
            if report.summary.failed_cases:
                print("BLOKE: one or more infrastructure or pipeline failures occurred.")
    except Exception:  # noqa: BLE001 - do not expose provider internals in benchmark output
        print("BLOKE: benchmark RAG service could not be initialized.")


if __name__ == "__main__":
    asyncio.run(main())
