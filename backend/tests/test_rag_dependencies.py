from app.api.dependencies import rag


def test_ollama_client_disables_environment_proxy_settings(monkeypatch):
    calls: list[dict[str, object]] = []
    sentinel = object()

    def create_client(**kwargs: object) -> object:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(rag.httpx, "AsyncClient", create_client)

    assert rag.create_ollama_client() is sentinel
    assert calls == [{"trust_env": False}]
